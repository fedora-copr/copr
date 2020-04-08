# coding: utf-8
import json
from multiprocessing import Process
from threading import Thread
import time
from setproctitle import setproctitle

from copr_backend.exceptions import VmDescriptorNotFound
from copr_backend.helpers import get_redis_logger
from copr_backend.vm_manage import VmStates, PUBSUB_MB, EventTopics


class Recycle(Thread):
    """
    Cleanup vmm services, now only terminator
    :param vmm:
    :return:
    """
    def __init__(self, terminator, recycle_period, *args, **kwargs):
        self.terminator = terminator
        self.recycle_period = int(recycle_period)
        super(Recycle, self).__init__(*args, **kwargs)
        self._running = False

    def run(self):

        self._running = True
        while self._running:
            time.sleep(self.recycle_period)
            self.terminator.recycle()

    def terminate(self):
        self._running = False

# KEYS[1]: VMD key
on_health_check_success_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state ~= "check_health" and old_state ~= "in_use" then
    return nil
else
    redis.call("HSET", KEYS[1], "check_fails", 0)
    if old_state == "check_health" then
        redis.call("HSET", KEYS[1], "state", "{}")
    end
end
""".format(VmStates.READY)

# KEYS[1]: VMD key
record_failure_lua = """
local old_state = redis.call("HGET", KEYS[1], "state")
if old_state ~= "check_health" and old_state ~= "in_use" and old_state ~= "check_health_failed" then
    return nil
else
    redis.call("HINCRBY", KEYS[1], "check_fails", 1)
    if old_state == "check_health" then
        redis.call("HSET", KEYS[1], "state", "{}")
    end
end
""".format(VmStates.CHECK_HEALTH_FAILED)


class EventHandler(Process):
    """
    :type vmm: VmManager
    """
    def __init__(self, opts, vmm, terminator):
        super(EventHandler, self).__init__(name="EventHandler")
        self.opts = opts
        self.vmm = vmm

        self.terminator = terminator

        self.kill_received = False

        # self.do_recycle_proc = None
        self.handlers_map = {
            EventTopics.HEALTH_CHECK: self.on_health_check_result,
            EventTopics.VM_SPAWNED: self.on_vm_spawned,
            EventTopics.VM_TERMINATION_REQUEST: self.on_vm_termination_request,
            EventTopics.VM_TERMINATED: self.on_vm_termination_result,
        }
        self.lua_scripts = {}
        self.recycle_period = 60

        self.log = get_redis_logger(self.vmm.opts, "vmm.event_handler", "vmm")
        self.vmm.set_logger(self.log)

    def post_init(self):
        # todo: move to manager.py, wrap call into VmManager methods
        self.lua_scripts["on_health_check_success"] = self.vmm.rc.register_script(on_health_check_success_lua)
        self.lua_scripts["record_failure"] = self.vmm.rc.register_script(record_failure_lua)

    def on_health_check_result(self, msg):
        try:
            vmd = self.vmm.get_vm_by_name(msg["vm_name"])
            check_fails_count = int(vmd.get_field(self.vmm.rc, "check_fails") or 0)
        except VmDescriptorNotFound:
            self.log.debug("VM record disappeared, ignoring health check results,  msg: %s", msg)
            return

        if msg["result"] == "OK":
            self.lua_scripts["on_health_check_success"](keys=[vmd.vm_key], args=[time.time()])
            self.log.debug("recording success for ip:%s name:%s", vmd.vm_ip, vmd.vm_name)
        else:
            self.log.debug("recording check fail: %s", msg)
            self.lua_scripts["record_failure"](keys=[vmd.vm_key])
            fails_count = int(vmd.get_field(self.vmm.rc, "check_fails") or 0)
            max_check_fails = self.opts.build_groups[vmd.group]["vm_max_check_fails"]
            if fails_count > max_check_fails:
                self.log.info("check fail threshold reached: %s, terminating: %s",
                              check_fails_count, msg)
                self.vmm.start_vm_termination(vmd.vm_name)

    def on_vm_spawned(self, msg):
        self.vmm.add_vm_to_pool(vm_ip=msg["vm_ip"], vm_name=msg["vm_name"], group=msg["group"])

    def on_vm_termination_request(self, msg):
        self.terminator.terminate_vm(vm_ip=msg["vm_ip"], vm_name=msg["vm_name"], group=msg["group"])

    def on_vm_termination_result(self, msg):
        if msg["result"] == "OK" and "vm_name" in msg:
            self.log.debug("Vm terminated, removing from pool ip: %s, name: %s, msg: %s",
                           msg.get("vm_ip"), msg.get("vm_name"), msg.get("msg"))
            self.vmm.remove_vm_from_pool(msg["vm_name"])
        elif "vm_name" not in msg:
            self.log.debug("Vm termination event missing vm name, msg: %s", msg)
        else:
            self.log.debug("Vm termination failed ip: %s, name: %s, msg: %s",
                           msg.get("vm_ip"), msg.get("vm_name"), msg.get("msg"))

    def run(self):
        setproctitle("Event Handler")

        self.do_recycle_proc = Recycle(terminator=self.terminator, recycle_period=self.recycle_period)
        self.do_recycle_proc.start()

        self.start_listen()

    def terminate(self):
        self.kill_received = True
        self.do_recycle_proc.terminate()
        self.do_recycle_proc.join()

    def start_listen(self):
        """
        Listens redis pubsub and perform requested actions.
        Message payload is packed in json, it should be a dictionary
            at the root level with reserved field `topic` which is required
            for message routing
        :type vmm: VmManager
        """
        channel = self.vmm.rc.pubsub(ignore_subscribe_messages=True)
        channel.subscribe(PUBSUB_MB)
        # TODO: check subscribe success
        self.log.info("Spawned pubsub handler")
        for raw in channel.listen():
            if self.kill_received:
                break
            if raw is None:
                continue
            else:
                if "type" not in raw or raw["type"] != "message" or "data" not in raw:
                    continue
                try:
                    msg = json.loads(raw["data"])

                    if "topic" not in msg:
                        raise Exception("Handler received msg without `topic` field, msg: {}".format(msg))
                    topic = msg["topic"]
                    if topic not in self.handlers_map:
                        raise Exception("Handler received msg with unknown `topic` field, msg: {}".format(msg))

                    self.handlers_map[topic](msg)

                except Exception as err:
                    self.log.exception("Handler error: raw msg: %s, %s", raw, err)
