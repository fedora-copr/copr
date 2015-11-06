# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import json

from multiprocessing import Process
import time
from setproctitle import setproctitle
import traceback
import psutil

from ..constants import JOB_GRAB_TASK_END_PUBSUB
from ..vm_manage import VmStates
from ..exceptions import VmSpawnLimitReached

from ..helpers import get_redis_logger


class VmMaster(Process):
    """
    Spawns and terminate VM for builder process.

    :type vmm: backend.vm_manage.manager.VmManager
    :type spawner: backend.vm_manage.spawn.Spawner
    :type checker: backend.vm_manage.check.HealthChecker
    """
    def __init__(self, opts, vmm, spawner, checker):
        super(VmMaster, self).__init__(name="vm_master")

        self.opts = opts
        self.vmm = vmm
        self.spawner = spawner
        self.checker = checker

        self.kill_received = False

        self.log = get_redis_logger(self.opts, "vmm.vm_master", "vmm")
        self.vmm.set_logger(self.log)

    def remove_old_dirty_vms(self):
        # terminate vms bound_to user and time.time() - vm.last_release_time > threshold_keep_vm_for_user_timeout
        #  or add field to VMD ot override common threshold
        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.READY]):
            if vmd.get_field(self.vmm.rc, "bound_to_user") is None:
                continue
            last_release = vmd.get_field(self.vmm.rc, "last_release")
            if last_release is None:
                continue
            not_re_acquired_in = time.time() - float(last_release)
            if not_re_acquired_in > self.opts.build_groups[vmd.group]["vm_dirty_terminating_timeout"]:
                self.log.info("dirty VM `{}` not re-acquired in {}, terminating it"
                              .format(vmd.vm_name, not_re_acquired_in))
                self.vmm.start_vm_termination(vmd.vm_name, allowed_pre_state=VmStates.READY)

    def request_build_reschedule(self, vmd):
        self.log.info("trying to publish reschedule")
        vmd_dict = vmd.to_dict()
        if all(x in vmd_dict for x in ["build_id", "task_id", "chroot"]):
            request = {
                "action": "reschedule",
                "build_id": vmd.build_id,
                "task_id": vmd.task_id,
                "chroot": vmd.chroot,
            }
            self.log.info("trying to publish reschedule: {}".format(request))
            self.vmm.rc.publish(JOB_GRAB_TASK_END_PUBSUB, json.dumps(request))
            # else:
            # self.log.info("Failed to  release VM: {}".format(vmd.vm_name))

    def check_one_vm_for_dead_builder(self, vmd):
        # TODO: builder should renew lease periodically
        # and we should use that time instead of in_use_since and pid checks
        in_use_since = vmd.get_field(self.vmm.rc, "in_use_since")
        pid = vmd.get_field(self.vmm.rc, "used_by_pid")

        if not in_use_since or not pid:
            return
        in_use_time_elapsed = time.time() - float(in_use_since)

        # give a minute for worker to set correct title
        if in_use_time_elapsed < 60 and str(pid) == "None":
            return

        pid = int(pid)
        # try:
        #     # here we can catch race condition: worker acquired VM but haven't set process title yet
        #     if psutil.pid_exists(pid) and vmd.vm_name in psutil.Process(pid).cmdline[0]:
        #         return
        #
        #     self.log.info("Process `{}` not exists anymore, doing second try. VM data: {}"
        #                   .format(pid, vmd))
        #     # dirty hack: sleep and check again
        #     time.sleep(5)
        #     if psutil.pid_exists(pid) and vmd.vm_name in psutil.Process(pid).cmdline[0]:
        #         return
        # except Exception:
        #     self.log.exception("Failed do determine if process `{}` still alive for VM: {}, assuming alive"
        #                        .format(pid, vmd))
        #     return

        # psutil changed Process().cmdline from property to function between f20 and f22
        # disabling more precise check for now
        try:
            # here we can catch race condition: worker acquired VM but haven't set process title yet
            if psutil.pid_exists(pid):
                return

            self.log.info("Process `{}` not exists anymore, doing second try. VM data: {}"
                          .format(pid, vmd))
            # dirty hack: sleep and check again
            time.sleep(5)
            if psutil.pid_exists(pid):
                return

        except Exception:
            self.log.exception("Failed do determine if process `{}` still alive for VM: {}, assuming alive"
                               .format(pid, vmd))
            return

        self.log.info("Process `{}` not exists anymore, terminating VM: {} ".format(pid, vmd.vm_name))
        self.vmm.start_vm_termination(vmd.vm_name, allowed_pre_state=VmStates.IN_USE)
        # cause race condition
        #  self.request_build_reschedule(vmd)

    def remove_vm_with_dead_builder(self):
        # TODO: rewrite build manage at backend and move functionality there
        # VMM shouldn't do this

        # check that process who acquired VMD still exists, otherwise release VM
        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.IN_USE]):
            self.check_one_vm_for_dead_builder(vmd)

    def check_vms_health(self):
        # for machines in state ready and time.time() - vm.last_health_check > threshold_health_check_period
        states_to_check = [VmStates.CHECK_HEALTH_FAILED, VmStates.READY,
                           VmStates.GOT_IP, VmStates.IN_USE]

        for vmd in self.vmm.get_vm_by_group_and_state_list(None, states_to_check):
            last_health_check = vmd.get_field(self.vmm.rc, "last_health_check")
            check_period = self.opts.build_groups[vmd.group]["vm_health_check_period"]
            if not last_health_check or time.time() - float(last_health_check) > check_period:
                self.start_vm_check(vmd.vm_name)

    def start_vm_check(self, vm_name):
        """
        Start VM health check sub-process if current VM state allows it
        """

        vmd = self.vmm.get_vm_by_name(vm_name)
        orig_state = vmd.state

        if self.vmm.lua_scripts["set_checking_state"](keys=[vmd.vm_key], args=[time.time()]) == "OK":
            # can start
            try:
                self.checker.run_check_health(vmd.vm_name, vmd.vm_ip)
            except Exception as err:
                self.log.exception("Failed to start health check: {}".format(err))
                if orig_state != VmStates.IN_USE:
                    vmd.store_field(self.vmm.rc, "state", orig_state)

        else:
            self.log.debug("Failed to start vm check, wrong state")
            return False

    def _check_total_running_vm_limit(self, group):
        """ Checks that number of VM in any state excluding Terminating plus
        number of running spawn processes is less than
        threshold defined by BackendConfig.build_group[group]["max_vm_total"]
        """
        active_vmd_list = self.vmm.get_vm_by_group_and_state_list(
            group, [VmStates.GOT_IP, VmStates.READY, VmStates.IN_USE,
                    VmStates.CHECK_HEALTH, VmStates.CHECK_HEALTH_FAILED])
        total_vm_estimation = len(active_vmd_list) + self.spawner.get_proc_num_per_group(group)
        if total_vm_estimation >= self.opts.build_groups[group]["max_vm_total"]:
            raise VmSpawnLimitReached(
                "Skip spawn for group {}: max total vm reached: vm count: {}, spawn process: {}"
                .format(group, len(active_vmd_list), self.spawner.get_proc_num_per_group(group)))

    def _check_elapsed_time_after_spawn(self, group):
        """ Checks that time elapsed since latest VM spawn attempt is greater than
        threshold defined by BackendConfig.build_group[group]["vm_spawn_min_interval"]
        """
        last_vm_spawn_start = self.vmm.read_vm_pool_info(group, "last_vm_spawn_start")
        if last_vm_spawn_start:
            time_elapsed = time.time() - float(last_vm_spawn_start)
            if time_elapsed < self.opts.build_groups[group]["vm_spawn_min_interval"]:
                raise VmSpawnLimitReached(
                    "Skip spawn for group {}: time after previous spawn attempt "
                    "< vm_spawn_min_interval: {}<{}"
                    .format(group, time_elapsed, self.opts.build_groups[group]["vm_spawn_min_interval"]))

    def _check_number_of_running_spawn_processes(self, group):
        """ Check that number of running spawn processes is less than
        threshold defined by BackendConfig.build_group[]["max_spawn_processes"]
        """
        if self.spawner.get_proc_num_per_group(group) >= self.opts.build_groups[group]["max_spawn_processes"]:
            raise VmSpawnLimitReached(
                "Skip spawn for group {}: reached maximum number of spawning processes: {}"
                .format(group, self.spawner.get_proc_num_per_group(group)))

    def _check_total_vm_limit(self, group):
        """ Check that number of running spawn processes is less than
        threshold defined by BackendConfig.build_group[]["max_spawn_processes"]
        """
        count_all_vm = len(self.vmm.get_all_vm_in_group(group))
        if count_all_vm >= 2 * self.opts.build_groups[group]["max_vm_total"]:
            raise VmSpawnLimitReached(
                "Skip spawn for group {}: #(ALL VM) >= 2 * max_vm_total reached: {}"
                .format(group, count_all_vm))

    def try_spawn_one(self, group):
        """
        Starts spawning process if all conditions are satisfied
        """
        # TODO: add setting "max_vm_in_ready_state", when this number reached, do not spawn more VMS, min value = 1

        try:
            self._check_total_running_vm_limit(group)
            self._check_elapsed_time_after_spawn(group)
            self._check_number_of_running_spawn_processes(group)
            self._check_total_vm_limit(group)
        except VmSpawnLimitReached as err:
            self.log.debug(err.msg)
            return

        self.log.info("Start spawning new VM for group: {}".format(self.opts.build_groups[group]["name"]))
        self.vmm.write_vm_pool_info(group, "last_vm_spawn_start", time.time())
        try:
            self.spawner.start_spawn(group)
        except Exception as error:
            self.log.exception("Error during spawn attempt: {}".format(error))

    def start_spawn_if_required(self):
        for group in self.vmm.vm_groups:
            self.try_spawn_one(group)

    def do_cycle(self):
        self.log.debug("starting do_cycle")

        # TODO: each check should be executed in threads ... and finish with join?

        self.remove_old_dirty_vms()
        self.check_vms_health()
        self.start_spawn_if_required()

        self.remove_vm_with_dead_builder()
        self.finalize_long_health_checks()
        self.terminate_again()

        self.spawner.recycle()

        # todo: self.terminate_excessive_vms() -- for case when config changed during runtime

    def run(self):
        if any(x is None for x in [self.spawner, self.checker]):
            raise RuntimeError("provide Spawner and HealthChecker "
                               "to run VmManager daemon")

        setproctitle("VM master")
        self.vmm.mark_server_start()
        self.kill_received = False

        self.log.info("VM master process started")
        while not self.kill_received:
            time.sleep(self.opts.vm_cycle_timeout)
            try:
                self.do_cycle()
            except Exception as err:
                self.log.error("Unhandled error: {}, {}".format(err, traceback.format_exc()))

    def terminate(self):
        self.kill_received = True
        if self.spawner is not None:
            self.spawner.terminate()
        if self.checker is not None:
            self.checker.terminate()

    def finalize_long_health_checks(self):
        """
        After server crash it's possible that some VM's will remain in `check_health` state
        Here we are looking for such records and mark them with `check_health_failed` state
        """
        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.CHECK_HEALTH]):

            time_elapsed = time.time() - float(vmd.get_field(self.vmm.rc, "last_health_check") or 0)
            if time_elapsed > self.opts.build_groups[vmd.group]["vm_health_check_max_time"]:
                self.log.info("VM marked with check fail state, "
                              "VM stayed too long in health check state, elapsed: {} VM: {}"
                              .format(time_elapsed, str(vmd)))
                self.vmm.mark_vm_check_failed(vmd.vm_name)

    def terminate_again(self):
        """
        If we failed to terminate instance request termination once more.
        Non-terminated instance detected as vm in the `terminating` state with
            time.time() - `terminating since` > Threshold
        It's possible, that VM was terminated but termination process doesn't receive confirmation from VM provider,
        but we have already got a new VM with the same IP => it's safe to remove old vm from pool
        """

        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.TERMINATING]):
            time_elapsed = time.time() - float(vmd.get_field(self.vmm.rc, "terminating_since") or 0)
            if time_elapsed > self.opts.build_groups[vmd.group]["vm_terminating_timeout"]:
                if len(self.vmm.lookup_vms_by_ip(vmd.vm_ip)) > 1:
                    self.log.info(
                        "Removing VM record: {}. There are more VM with the same ip, "
                        "it's safe to remove current one from VM pool".format(vmd.vm_name))
                    self.vmm.remove_vm_from_pool(vmd.vm_name)
                else:
                    self.log.info("Sent VM {} for termination again".format(vmd.vm_name))
                    self.vmm.start_vm_termination(vmd.vm_name, allowed_pre_state=VmStates.TERMINATING)
