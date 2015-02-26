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
import sys
import psutil

from backend.constants import DEF_BUILD_TIMEOUT, JOB_GRAB_TASK_END_PUBSUB
from backend.helpers import format_tb
from backend.vm_manage import VmStates, Thresholds, KEY_VM_POOL_INFO
from backend.vm_manage.event_handle import EventHandler


class VmMaster(Process):
    """
    Spawns and terminate VM for builder process. Mainly wrapper for ..vm_manage package.

    :type vm_manager: backend.vm_manage.manager.VmManager
    """
    def __init__(self, vm_manager):
        super(VmMaster, self).__init__(name="vm_master")

        self.opts = vm_manager.opts
        self.vmm = vm_manager
        self.log = vm_manager.log

        self.kill_received = False

        self.spawned_handler = None
        self.event_handler = None

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
            if not_re_acquired_in > Thresholds.dirty_vm_terminating_timeout:
                self.log("dirty VM `{}` not re-acquired in {}, terminating it"
                         .format(vmd.vm_name, not_re_acquired_in))
                self.vmm.start_vm_termination(vmd.vm_name, allowed_pre_state=VmStates.READY)

    def remove_vm_with_dead_builder(self):
        # check that process who acquired VMD still exists, otherwise release VM
        # TODO: fix 4 nested `if`. Ugly!
        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.IN_USE]):
            pid = vmd.get_field(self.vmm.rc, "used_by_pid")
            if str(pid) != "None":
                pid = int(pid)
                if not psutil.pid_exists(pid) or vmd.vm_name not in psutil.Process(pid).name:
                    self.log("Process `{}` not exists anymore, releasing VM: {} ".format(pid, str(vmd)))
                    if self.vmm.release_vm(vmd.vm_name):
                        vmd_dict = vmd.to_dict()
                        if all(x in vmd_dict for x in ["build_id", "task_id", "chroot"]):
                            request = {
                                "action": "reschedule",
                                "build_id": vmd.build_id,
                                "task_id": vmd.task_id,
                                "chroot": vmd.chroot,
                            }

                            self.vmm.rc.publish(JOB_GRAB_TASK_END_PUBSUB, json.dumps(request))

    def check_vms_health(self):
        # for machines in state ready and time.time() - vm.last_health_check > threshold_health_check_period
        states_to_check = [VmStates.CHECK_HEALTH_FAILED, VmStates.READY,
                           VmStates.GOT_IP, VmStates.IN_USE]

        for vmd in self.vmm.get_vm_by_group_and_state_list(None, states_to_check):
            last_health_check = vmd.get_field(self.vmm.rc, "last_health_check")
            if not last_health_check or time.time() - float(last_health_check) > Thresholds.health_check_period:
                self.vmm.start_vm_check(vmd.vm_name)

    def try_spawn_one(self, group):
        max_vm_total = self.opts.build_groups[group]["max_vm_total"]
        active_vmd_list = self.vmm.get_vm_by_group_and_state_list(
            group, [VmStates.GOT_IP, VmStates.READY, VmStates.IN_USE, VmStates.CHECK_HEALTH])

        # self.log("Spawner proc count: {}".format(self.vmm.spawner.children_number))
        #self.log("active VM#: {}".format(map(lambda x: (x.vm_name, x.state), active_vmd_list)))
        total_vm_estimation = len(active_vmd_list) + self.vmm.spawner.children_number
        if total_vm_estimation >= max_vm_total:
            self.log("Skip spawn: max total vm reached for group {}: vm count: {}, spawn process: {}"
                     .format(group, len(active_vmd_list), self.opts.build_groups[group]["max_vm_total"]))
            return
        last_vm_spawn_start = self.vmm.rc.hget(KEY_VM_POOL_INFO.format(group=group), "last_vm_spawn_start")
        if last_vm_spawn_start:
            time_elapsed = time.time() - float(last_vm_spawn_start)
            if time_elapsed < Thresholds.vm_spawn_min_interval:
                self.log("Skip spawn: time after previous spawn attempt < vm_spawn_min_interval: {}<{}"
                         .format(time_elapsed, Thresholds.vm_spawn_min_interval))
                return

        if self.vmm.spawner.children_number >= self.opts.build_groups[group]["max_spawn_processes"]:
            self.log("Skip spawn: reached maximum number of spawning processes: {}"
                     .format(self.vmm.spawner.children_number))
            return

        count_all_vm = len(self.vmm.get_all_vm_in_group(group))
        if count_all_vm >= 2 * self.opts.build_groups[group]["max_vm_total"]:
            self.log("Skip spawn: #(ALL VM) >= 2 * max_vm_total reached: {}"
                     .format(count_all_vm))
            return

        self.log("start spawning new VM for group: {}".format(self.opts.build_groups[group]["name"]))
        self.vmm.rc.hset(KEY_VM_POOL_INFO.format(group=group), "last_vm_spawn_start", time.time())
        try:
            self.vmm.spawner.start_spawn(group)
        except Exception as err:
            _, _, ex_tb = sys.exc_info()
            self.log("Error during spawn attempt: {} {}".format(err, format_tb(err, ex_tb)))

    def start_spawn_if_required(self):
        for group in self.vmm.vm_groups:
            self.try_spawn_one(group)

    def do_cycle(self):
        self.log("starting do_cycle")

        # TODO: each check should be executed in threads ... and finish with join?
        # self.terminate_abandoned_vms()
        self.remove_old_dirty_vms()
        self.check_vms_health()
        self.start_spawn_if_required()

        self.finalize_long_health_checks()
        self.terminate_again()

        self.vmm.spawner.recycle()

        # todo: self.terminate_excessive_vms() -- for case when config changed during runtime

        # todo: self.terminate_old_unchecked_vms()

    def run(self):
        if self.vmm.spawner is None or self.vmm.terminator is None or self.vmm.checker is None:
            raise RuntimeError("provide Spawner and Terminator to run VmManager daemon")

        setproctitle("VM master")

        self.kill_received = False

        self.event_handler = EventHandler(self.vmm)
        self.event_handler.start()

        while not self.kill_received:
            time.sleep(Thresholds.cycle_timeout)
            try:
                self.do_cycle()
            except Exception as err:
                self.log("Unhandled error: {}, {}".format(err, traceback.format_exc()))

    def terminate(self):
        self.kill_received = True
        if self.event_handler:
            self.event_handler.terminate()
            self.event_handler.join()

    def finalize_long_health_checks(self):
        """
        After server crash it's possible that some VM's will remain in `check_health` state
        Here we are looking for such records and mark them with `check_health_failed` state
        """
        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.CHECK_HEALTH]):

            time_elapsed = time.time() - float(vmd.get_field(self.vmm.rc, "last_health_check") or 0)
            # self.log("Checking for long health check, elapsed: {} VM: {}".format(time_elapsed, str(vmd)))
            if time_elapsed > Thresholds.health_check_max_time:
                self.vmm.mark_vm_check_failed(vmd.vm_name)

    def terminate_again(self):
        """
        If we failed to terminate instance request termination once more.
        Non-terminated instance detected as vm in the `terminating` state with time.time() - `terminating since` > Threshold
        It's possible, that VM was terminated but termination process doesn't receive confirmation from VM provider,
        but we have already got a new VM with the same IP => it's safe to remove old vm from pool
        :return:
        """

        for vmd in self.vmm.get_vm_by_group_and_state_list(None, [VmStates.TERMINATING]):
            time_elapsed = time.time() - float(vmd.get_field(self.vmm.rc, "terminating_since") or 0)
            if time_elapsed > Thresholds.terminating_timeout:
                if len(self.vmm.lookup_vms_by_ip(vmd.vm_ip)) > 1:
                    # there are more VM with the same ip, it's safe to remove current one from VM pool
                    self.vmm.remove_vm_from_pool(vmd.vm_name)
                else:
                    self.vmm.start_vm_termination(vmd.vm_name, allowed_pre_state=VmStates.TERMINATING)
