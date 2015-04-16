# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

from itertools import chain
import json
import time
import weakref
from cStringIO import StringIO
import datetime
from backend.exceptions import VmError, NoVmAvailable

from backend.helpers import get_redis_connection
from .models import VmDescriptor
from . import VmStates, KEY_VM_INSTANCE, KEY_VM_POOL, EventTopics, PUBSUB_MB, KEY_SERVER_INFO, PUBSUB_INTERRUPT_BUILDER
from ..helpers import get_redis_logger

# KEYS[1]: VMD key
# ARGV[1] current timestamp for `last_health_check`
set_checking_state_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state ~= "got_ip" and old_state ~= "ready" and old_state ~= "in_use" and old_state ~= "check_health_failed" then
    return nil
else
    if old_state ~= "in_use" then
        redis.call("HSET", KEYS[1], "state", "check_health")
    end
    redis.call("HSET", KEYS[1], "last_health_check", ARGV[1])
    return "OK"
end
"""

# KEYS[1]: VMD key
# ARGV[1]: user to bound;
# ARGV[2]: pid of the builder process
# ARGV[3]: current timestamp for `in_use_since`
# ARGV[4]: task_id
# ARGV[5]: build_id
# ARGV[6]: chroot
acquire_vm_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state ~= "ready"  then
    return nil
else
    local last_health_check = tonumber(redis.call("HGET", KEYS[1], "last_health_check"))
    local server_restart_time = tonumber(redis.call("HGET", KEYS[2], "server_start_timestamp"))
    if last_health_check and server_restart_time and last_health_check > server_restart_time  then
        redis.call("HMSET", KEYS[1], "state", "in_use", "bound_to_user", ARGV[1],
                   "used_by_pid", ARGV[2], "in_use_since", ARGV[3],
                   "task_id",  ARGV[4], "build_id", ARGV[5], "chroot", ARGV[6])
        return "OK"
    else
        return nil
    end
end
"""

# KEYS[1]: VMD key
# ARGV[1] current timestamp for `last_release`
release_vm_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state ~= "in_use" then
    return nil
else
    redis.call("HMSET", KEYS[1], "state", "ready", "last_release", ARGV[1])
    redis.call("HDEL", KEYS[1], "in_use_since", "used_by_pid", "task_id", "build_id", "chroot")
    redis.call("HINCRBY", KEYS[1], "builds_count", 1)

    local check_fails = tonumber(redis.call("HGET", KEYS[1], "check_fails"))
    if check_fails > 0 then
        redis.call("HSET", KEYS[1], "state", "check_health_failed")
    end

    return "OK"
end
"""

# KEYS [1]: VMD key
# ARGS [1]: allowed_pre_state
# ARGS [2]: timestamp for `terminating_since`
terminate_vm_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")

if ARGV[1] and ARGV[1] ~= "None" and old_state ~= ARGV[1] then
    return "Old state != `allowed_pre_state`"
elseif old_state == "terminating" and ARGV[1] ~= "terminating" then
    return "Already terminating"
else
    redis.call("HMSET", KEYS[1], "state", "terminating", "terminating_since", ARGV[2])
    return "OK"
end
"""

mark_vm_check_failed_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state == "check_health" then
    redis.call("HMSET", KEYS[1], "state", "check_health_failed")
    return "OK"
end
"""


class VmManager(object):
    """
    VM manager, it is used for two purposes:
    - Daemon which control VMs lifecycle, requires params `spawner,terminator`
    - Client to acquire and release VM in builder process

    :param opts: Global backend configuration
    :type opts: Bunch

    :type logger: logging.Logger
    :param logger: Logger instance to use inside of manager, if None manager would create
        new logger using helpers.get_redis_logger

    :param checker: object with method `check_health(ip) -> None or raise exception`
    :param spawner: object with method `spawn() -> IP or raise exception`
    :param terminator: object with safe method `terminate(ip, vm_name)`
    """
    def __init__(self, opts, logger=None, checker=None, spawner=None, terminator=None):

        self.opts = weakref.proxy(opts)

        self.checker = checker
        self.spawner = spawner
        self.terminator = terminator

        self.lua_scripts = {}

        self.rc = None
        self.log = logger or get_redis_logger(self.opts, "vmm.lib", "vmm")

    def post_init(self):
        """
        Self configuration. Should be called before usage of some methods.
        """

        self.rc = get_redis_connection(self.opts)
        self.lua_scripts["set_checking_state"] = self.rc.register_script(set_checking_state_lua)
        self.lua_scripts["acquire_vm"] = self.rc.register_script(acquire_vm_lua)
        self.lua_scripts["release_vm"] = self.rc.register_script(release_vm_lua)
        self.lua_scripts["terminate_vm"] = self.rc.register_script(terminate_vm_lua)
        self.lua_scripts["mark_vm_check_failed"] = self.rc.register_script(mark_vm_check_failed_lua)

    def set_logger(self, logger):
        """
        :param logger: Logger to be used by manager
        :type logger: logging.Logger
        """
        self.log = logger

    @property
    def vm_groups(self):
        """
        :return: VM build groups
        :rtype: list of int
        """
        return range(self.opts.build_groups_count)

    def add_vm_to_pool(self, vm_ip, vm_name, group):
        """
        Adds newly spawned VM into the pool of available builders

        :param str vm_ip: IP
        :param str vm_name: VM name
        :param group: builder group
        :type group: int
        :rtype: VmDescriptor
        """
        # print("\n ADD VM TO POOL")
        if self.rc.sismember(KEY_VM_POOL.format(group=group), vm_name):
            raise VmError("Can't add VM `{}` to the pool, such name already used".format(vm_name))

        vmd = VmDescriptor(vm_ip, vm_name, group, VmStates.GOT_IP)
        # print("VMD: {}".format(vmd))
        pipe = self.rc.pipeline()
        pipe.sadd(KEY_VM_POOL.format(group=group), vm_name)
        pipe.hmset(KEY_VM_INSTANCE.format(vm_name=vm_name), vmd.to_dict())
        pipe.execute()
        self.log.info("registered new VM: {} {}".format(vmd.vm_name, vmd.vm_ip))
        return vmd

    def lookup_vms_by_ip(self, vm_ip):
        """
        :param vm_ip:
        :return: List of found VMD with the give ip
        :rtype: list of VmDescriptor
        """
        return [
            vmd for vmd in self.get_all_vm()
            if vmd.vm_ip == vm_ip
        ]

    def start_vm_check(self, vm_name):
        """
        Start VM health check sub-process if current VM state allows it
        """

        vmd = self.get_vm_by_name(vm_name)
        orig_state = vmd.state

        if self.lua_scripts["set_checking_state"](keys=[vmd.vm_key], args=[time.time()]) == "OK":
            # can start
            try:
                self.checker.run_check_health(vmd.vm_name, vmd.vm_ip)
            except Exception as err:
                self.log.exception("Failed to start health check: {}".format(err))
                if orig_state != VmStates.IN_USE:
                    vmd.store_field(self.rc, "state", orig_state)

        else:
            self.log.debug("Failed to start vm check, wrong state")
            return False

    def mark_vm_check_failed(self, vm_name):
        vm_key = KEY_VM_INSTANCE.format(vm_name=vm_name)
        self.lua_scripts["mark_vm_check_failed"](keys=[vm_key])

    def mark_server_start(self):
        self.rc.hset(KEY_SERVER_INFO, "server_start_timestamp", time.time())

    def can_user_acquire_more_vm(self, username, group):
        """
        :return bool: True when user are allowed to acquire more VM
        """
        vmd_list = self.get_all_vm_in_group(group)
        vm_count_used_by_user = len([
            vmd for vmd in vmd_list if
            vmd.bound_to_user == username and vmd.state == VmStates.IN_USE
        ])
        self.log.debug("# vm by user: {}, limit:{} ".format(
            vm_count_used_by_user, self.opts.build_groups[group]["max_vm_per_user"]
        ))
        if vm_count_used_by_user >= self.opts.build_groups[group]["max_vm_per_user"]:
            # TODO: this check isn't reliable, if two (or more) processes check VM list
            # at the +- same time, they could acquire more VMs
            #  proper solution: do this check inside lua script
            self.log.debug("No VM are available, user `{}` already acquired #{} VMs"
                           .format(username, vm_count_used_by_user))
            return False
        else:
            return True

    def acquire_vm(self, group, username, pid, task_id=None, build_id=None, chroot=None):
        """
        Try to acquire VM from pool

        :param group: builder group id, as defined in config
        :type group: int
        :param username: build owner username, VMM prefer to reuse an existing VM which was used by the same user
        :param pid: builder pid to release VM after build process unhandled death

        :rtype: VmDescriptor
        :raises: NoVmAvailable  when manager couldn't find suitable VM for the given group and user
        """
        vmd_list = self.get_all_vm_in_group(group)
        if not self.can_user_acquire_more_vm(username, group):
            raise NoVmAvailable("No VM are available, user `{}` already acquired too much VMs"
                                .format(username))

        ready_vmd_list = [vmd for vmd in vmd_list if vmd.state == VmStates.READY]
        # trying to find VM used by this user
        dirtied_by_user = [vmd for vmd in ready_vmd_list if vmd.bound_to_user == username]
        clean_list = [vmd for vmd in ready_vmd_list if vmd.bound_to_user is None]
        all_vms = list(chain(dirtied_by_user, clean_list))

        for vmd in all_vms:
            if vmd.get_field(self.rc, "check_fails") != "0":
                self.log.debug("VM {} has check fails, skip acquire".format(vmd.vm_name))
            vm_key = KEY_VM_INSTANCE.format(vm_name=vmd.vm_name)
            if self.lua_scripts["acquire_vm"](keys=[vm_key, KEY_SERVER_INFO],
                                              args=[username, pid, time.time(),
                                                    task_id, build_id, chroot]) == "OK":
                self.log.info("Acquired VM :{} {} for pid: {}".format(vmd.vm_name, vmd.vm_ip, pid))
                return vmd
        else:
            raise NoVmAvailable("No VM are available, please wait in queue. Group: {}".format(group))

    def release_vm(self, vm_name):
        """
        Return VM into the pool.
        :return: True if successful
        :rtype: bool
        """
        # in_use -> ready
        self.log.info("Releasing VM {}".format(vm_name))
        vm_key = KEY_VM_INSTANCE.format(vm_name=vm_name)
        lua_result = self.lua_scripts["release_vm"](keys=[vm_key], args=[time.time()])
        self.log.debug("release vm result `{}`".format(lua_result))
        return lua_result == "OK"

    def start_vm_termination(self, vm_name, allowed_pre_state=None):
        """
        Initiate VM termination process using redis publish.

        :param allowed_pre_state: When defined force check that old state is among allowed ones.
        :type allowed_pre_state: str constant from VmState
        """
        vmd = self.get_vm_by_name(vm_name)
        lua_result = self.lua_scripts["terminate_vm"](keys=[vmd.vm_key], args=[allowed_pre_state, time.time()])
        if lua_result == "OK":
            msg = {
                "group": vmd.group,
                "vm_ip": vmd.vm_ip,
                "vm_name": vmd.vm_name,
                "topic": EventTopics.VM_TERMINATION_REQUEST
            }
            self.rc.publish(PUBSUB_MB, json.dumps(msg))
            self.log.info("VM {} queued for termination".format(vmd.vm_name))

            # TODO: remove when refactored build management
            # self.rc.publish(PUBSUB_INTERRUPT_BUILDER.format(vmd.vm_ip), "vm died")
        else:
            self.log.debug("VM  termination `{}` skipped due to: {} ".format(vm_name, lua_result))

    def remove_vm_from_pool(self, vm_name):
        """
        Backend forgets about VM after this method

        :raises VmError: if VM has wrong state
        """
        vmd = self.get_vm_by_name(vm_name)
        if vmd.get_field(self.rc, "state") != VmStates.TERMINATING:
            raise VmError("VM should have `terminating` state to be removable")
        pipe = self.rc.pipeline()
        pipe.srem(KEY_VM_POOL.format(group=vmd.group), vm_name)
        pipe.delete(KEY_VM_INSTANCE.format(vm_name=vm_name))
        pipe.execute()
        self.log.info("removed vm `{}` from pool".format(vm_name))

    def get_all_vm_in_group(self, group):
        """
        :rtype: list of VmDescriptor
        """
        vm_name_list = self.rc.smembers(KEY_VM_POOL.format(group=group))
        return [VmDescriptor.load(self.rc, vm_name) for vm_name in vm_name_list]

    def get_all_vm(self):
        """
        :rtype: list of VmDescriptor
        """
        vm_name_list = []
        for group in self.vm_groups:
            vm_name_list.extend(self.rc.smembers(KEY_VM_POOL.format(group=group)))
        return [VmDescriptor.load(self.rc, vm_name) for vm_name in vm_name_list]

    def get_vm_by_name(self, vm_name):
        """
        :rtype: VmDescriptor
        """
        return VmDescriptor.load(self.rc, vm_name)

    def get_vm_by_group_and_state_list(self, group, state_list):
        """
        Select VM-s for the given group and allowed states

        :param group: filter VM-s by the build group. If ``group is None`` select VM-s from the all groups
        :param state_list: VM state should be in the ``state_list``.

        :return: Filtered VM-s
        :rtype: list of VmDescriptor
        """
        states = set(state_list)
        if group is None:
            vmd_list = self.get_all_vm()
        else:
            vmd_list = self.get_all_vm_in_group(group)
        return [vmd for vmd in vmd_list if vmd.state in states]

    def info(self):
        """
        Present information about all managed VMs in a human readable form.

        :rtype: str
        """
        dt_fields = {
            "last_health_check",
            "in_use_since",
        }

        buf = StringIO()
        for group_id in self.vm_groups:
            bg = self.opts.build_groups[group_id]
            buf.write("=" * 32)
            header = "\nVM group #{} {} archs: {}\n===\n".format(group_id, bg["name"], bg["archs"])
            buf.write(header)
            vmd_list = self.get_all_vm_in_group(group_id)
            for vmd in vmd_list:
                buf.write("\t VM {}, ip: {}\n".format(vmd.vm_name, vmd.vm_ip))
                for k, v in vmd.to_dict().items():
                    if k in ["vm_name", "vm_ip", "group"]:
                        continue
                    if k in dt_fields:
                        v = str(datetime.datetime.fromtimestamp(float(v)))
                    buf.write("\t\t{}: {}\n".format(k, v))
                buf.write("\n")

            buf.write("\n")
        return buf.getvalue()
