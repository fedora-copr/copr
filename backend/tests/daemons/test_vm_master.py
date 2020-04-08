# coding: utf-8

import copy

from collections import defaultdict
import json
from random import choice
import types
from munch import Munch
import time
from multiprocessing import Queue


import tempfile
import shutil
import os

from copr_backend.helpers import get_redis_connection
from copr_backend.vm_manage import VmStates
from copr_backend.vm_manage.manager import VmManager
from copr_backend.daemons.vm_master import VmMaster
from copr_backend.exceptions import VmError, VmSpawnLimitReached

from unittest import mock, skip
from unittest.mock import patch, MagicMock
import pytest

# TODO: drop these, these are not needed nowadays
JOB_GRAB_TASK_END_PUBSUB = "unused"


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "copr_backend.daemons.vm_master"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_psutil():
    with mock.patch("{}.psutil".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_setproctitle():
    with mock.patch("{}.setproctitle".format(MODULE_REF)) as handle:
        yield handle


# @pytest.yield_fixture
# def mc_time_vmm():
#     with mock.patch("copr_backend.vm_manage.manager.time") as handle:
#         yield handle


class TestCallback(object):
    def log(self, msg):
        print(msg)


class TestVmMaster(object):

    def setup_method(self, method):
        self.vm_spawn_min_interval = 30

        self.opts = Munch(
            redis_host="127.0.0.1",
            redis_db=9,
            redis_port=7777,
            ssh=Munch(
                transport="ssh"
            ),
            build_groups_count=2,
            build_groups={
                0: {
                    "name": "base",
                    "archs": ["i386", "x86_64"],
                    "max_vm_total": 5,
                    "max_spawn_processes": 3,
                    "vm_spawn_min_interval": self.vm_spawn_min_interval,
                    "vm_dirty_terminating_timeout": 120,
                    "vm_health_check_period": 10,
                    "vm_health_check_max_time": 60,
                    "vm_terminating_timeout": 300,
                },
                1: {
                    "name": "arm",
                    "archs": ["armV7"],
                    "vm_spawn_min_interval": self.vm_spawn_min_interval,
                    "vm_dirty_terminating_timeout": 120,
                    "vm_health_check_period": 10,
                    "vm_health_check_max_time": 60,
                    "vm_terminating_timeout": 300,
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            vm_cycle_timeout=10,


        )

        self.queue = Queue()

        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"
        self.group = 0
        self.username = "bob"

        self.rc = get_redis_connection(self.opts)
        self.ps = None
        self.log_msg_list = []

        self.callback = TestCallback()
        # checker = HealthChecker(self.opts, self.callback)
        self.checker = MagicMock()
        self.spawner = MagicMock()
        self.terminator = MagicMock()

        self.mc_logger = MagicMock()
        self.vmm = VmManager(self.opts, logger=self.mc_logger)

        self.event_handler = MagicMock()
        self.vm_master = VmMaster(
            self.opts,
            self.vmm,
            self.spawner,
            self.checker,
        )
        self.vm_master.event_handler = MagicMock()
        self.pid = 12345

        self.vm_ip = "127.0.0.1"
        self.vm_name = "build 12345"

    def clean_redis(self):
        keys = self.vmm.rc.keys("*")
        if keys:
            self.vmm.rc.delete(*keys)

    def teardown_method(self, method):
        self.clean_redis()

    @pytest.fixture
    def add_vmd(self):
        self.vmd_a1 = self.vmm.add_vm_to_pool("127.0.0.1", "a1", 0)
        self.vmd_a2 = self.vmm.add_vm_to_pool("127.0.0.2", "a2", 0)
        self.vmd_a3 = self.vmm.add_vm_to_pool("127.0.0.3", "a3", 0)
        self.vmd_b1 = self.vmm.add_vm_to_pool("127.0.0.4", "b1", 1)
        self.vmd_b2 = self.vmm.add_vm_to_pool("127.0.0.5", "b2", 1)
        self.vmd_b3 = self.vmm.add_vm_to_pool("127.0.0.6", "b3", 1)

    def rcv_from_ps_message_bus(self):
        # don't forget to subscribe self.ps
        rcv_msg_list = []
        for i in range(10):
            msg = self.ps.get_message()
            if msg:
                rcv_msg_list.append(msg)
            time.sleep(0.01)
        return rcv_msg_list

    def test_pass(self, add_vmd):
        pass

    def test_remove_old_dirty_vms(self, mc_time, add_vmd):
        # pass
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        # VM in ready state, with not empty bount_to_user and (NOW - last_release) > threshold
        #   should be terminated
        for vmd in [self.vmd_a1, self.vmd_a2, self.vmd_b1, self.vmd_b2]:
            vmd.store_field(self.rc, "state", VmStates.READY)

        for vmd in [self.vmd_a1, self.vmd_a2, self.vmd_b1]:
            vmd.store_field(self.rc, "last_release", 0)

        for vmd in [self.vmd_a1, self.vmd_b1, self.vmd_b2]:
            vmd.store_field(self.rc, "bound_to_user", "user")

        for vmd in [self.vmd_a3, self.vmd_b3]:
            vmd.store_field(self.rc, "state", VmStates.IN_USE)

        mc_time.time.return_value = 1
        # no vm terminated
        self.vm_master.remove_old_dirty_vms()
        assert not self.vmm.start_vm_termination.called

        mc_time.time.return_value = self.opts.build_groups[0]["vm_dirty_terminating_timeout"] + 1

        # only "a1" and "b1" should be terminated
        self.vm_master.remove_old_dirty_vms()
        assert self.vmm.start_vm_termination.called
        terminated_names = set([call[0][1] for call
                               in self.vmm.start_vm_termination.call_args_list])
        assert set(["a1", "b1"]) == terminated_names

    def disabled_test_remove_vm_with_dead_builder(self, mc_time, add_vmd, mc_psutil):
        # todo: re-enable after psutil.Process.cmdline will be in use
        mc_time.time.return_value = time.time()
        self.vm_master.log = MagicMock()

        self.vmm.start_vm_termination = MagicMock()
        self.vmm.start_vm_termination.return_value = "OK"

        for idx, vmd in enumerate([self.vmd_a1, self.vmd_a2,
                                   self.vmd_b1, self.vmd_b2, self.vmd_b3]):
            vmd.store_field(self.rc, "state", VmStates.IN_USE)
            vmd.store_field(self.rc, "chroot", "fedora-20-x86_64")
            vmd.store_field(self.rc, "task_id", "{}-fedora-20-x86_64".format(idx + 1))
            vmd.store_field(self.rc, "build_id", idx + 1)
            vmd.store_field(self.rc, "in_use_since", 0)

        self.rc.hdel(self.vmd_b3.vm_key, "chroot")

        for idx, vmd in enumerate([self.vmd_a1, self.vmd_a2, self.vmd_b2, self.vmd_b3]):
            vmd.store_field(self.rc, "used_by_worker", idx + 1)

        for vmd in [self.vmd_a3, self.vmd_a3]:
            vmd.store_field(self.rc, "state", VmStates.READY)

        def mc_psutil_process(pid):
            p = MagicMock()
            mapping = {
                "1": "a1",
                "2": "a2",
                "3": "b1",
                "4": "None",
                "5": "None",
            }
            p.cmdline = ["builder vm_name={} suffix".format(mapping.get(str(pid))),]
            return p

        def mc_psutil_pid_exists(pid):
            if str(pid) in ["1", "4"]:
                return True

            return False

        mc_psutil.Process.side_effect = mc_psutil_process
        mc_psutil.pid_exists.side_effect = mc_psutil_pid_exists

        self.ps = self.vmm.rc.pubsub(ignore_subscribe_messages=True)
        self.ps.subscribe(JOB_GRAB_TASK_END_PUBSUB)
        self.vm_master.remove_vm_with_dead_builder()

        msg_list = self.rcv_from_ps_message_bus()
        assert self.vmm.start_vm_termination.call_args_list == [
            mock.call('a2', allowed_pre_state='in_use'),
            mock.call('b2', allowed_pre_state='in_use'),
            mock.call('b3', allowed_pre_state='in_use')
        ]
        # changed logic for the moment
        # assert set(["2", "4"]) == set([json.loads(m["data"])["build_id"] for m in msg_list])

    def test_check_vms_health(self, mc_time, add_vmd):
        self.vm_master.start_vm_check = types.MethodType(MagicMock(), self.vmm)
        for vmd in [self.vmd_a1, self.vmd_a2, self.vmd_a3, self.vmd_b1, self.vmd_b2, self.vmd_b3]:
            vmd.store_field(self.rc, "last_health_check", 0)

        self.vmd_a1.store_field(self.rc, "state", VmStates.IN_USE)
        self.vmd_a2.store_field(self.rc, "state", VmStates.CHECK_HEALTH)
        self.vmd_a3.store_field(self.rc, "state", VmStates.CHECK_HEALTH_FAILED)
        self.vmd_b1.store_field(self.rc, "state", VmStates.GOT_IP)
        self.vmd_b2.store_field(self.rc, "state", VmStates.READY)
        self.vmd_b3.store_field(self.rc, "state", VmStates.TERMINATING)

        mc_time.time.return_value = 1
        self.vm_master.check_vms_health()
        assert not self.vm_master.start_vm_check.called

        mc_time.time.return_value = 1 + self.opts.build_groups[0]["vm_health_check_period"]
        self.vm_master.check_vms_health()
        to_check = set(call[0][1] for call in self.vm_master.start_vm_check.call_args_list)
        assert set(['a1', 'a3', 'b1', 'b2']) == to_check

        self.vm_master.start_vm_check.reset_mock()
        for vmd in [self.vmd_a1, self.vmd_a2, self.vmd_a3, self.vmd_b1, self.vmd_b2, self.vmd_b3]:
            self.rc.hdel(vmd.vm_key, "last_health_check")

        self.vm_master.check_vms_health()
        to_check = set(call[0][1] for call in self.vm_master.start_vm_check.call_args_list)
        assert set(['a1', 'a3', 'b1', 'b2']) == to_check

    def test_finalize_long_health_checks(self, mc_time, add_vmd):

        mc_time.time.return_value = 0
        self.vmd_a1.store_field(self.rc, "state", VmStates.IN_USE)
        self.vmd_a2.store_field(self.rc, "state", VmStates.CHECK_HEALTH)
        self.vmd_a3.store_field(self.rc, "state", VmStates.CHECK_HEALTH)

        self.vmd_a2.store_field(self.rc, "last_health_check", 0)
        self.vmd_a3.store_field(self.rc, "last_health_check",
                                self.opts.build_groups[0]["vm_health_check_max_time"] + 10)

        mc_time.time.return_value = self.opts.build_groups[0]["vm_health_check_max_time"] + 11

        self.vmm.mark_vm_check_failed = MagicMock()
        self.vm_master.finalize_long_health_checks()
        assert self.vmm.mark_vm_check_failed.called_once
        assert self.vmm.mark_vm_check_failed.call_args[0][0] == "a2"

    def test_terminate_again(self, mc_time, add_vmd):
        mc_time.time.return_value = 0
        self.vmd_a1.store_field(self.rc, "state", VmStates.IN_USE)
        self.vmd_a2.store_field(self.rc, "state", VmStates.CHECK_HEALTH)
        self.vmd_a3.store_field(self.rc, "state", VmStates.READY)

        mc_time.time.return_value = 1
        self.vmm.remove_vm_from_pool = MagicMock()
        self.vmm.start_vm_termination = MagicMock()
        # case 1 no VM in terminating states =>
        #   no start_vm_termination, no remove_vm_from_pool
        # import ipdb; ipdb.set_trace()
        self.vm_master.terminate_again()
        assert not self.vmm.remove_vm_from_pool.called
        assert not self.vmm.start_vm_termination.called

        # case 2: one VM in terminating state with unique ip, time_elapsed < threshold
        #   no start_vm_termination, no remove_vm_from_pool
        self.vmd_a1.store_field(self.rc, "state", VmStates.TERMINATING)
        self.vmd_a1.store_field(self.rc, "terminating_since", 0)

        self.vm_master.terminate_again()
        assert not self.vmm.remove_vm_from_pool.called
        assert not self.vmm.start_vm_termination.called

        # case 3: one VM in terminating state with unique ip, time_elapsed > threshold
        #   start_vm_termination called, no remove_vm_from_pool
        mc_time.time.return_value = 1 + self.opts.build_groups[0]["vm_terminating_timeout"]

        self.vm_master.terminate_again()
        assert not self.vmm.remove_vm_from_pool.called
        assert self.vmm.start_vm_termination.called
        assert self.vmm.start_vm_termination.call_args[0][0] == self.vmd_a1.vm_name

        self.vmm.start_vm_termination.reset_mock()

        # case 4: two VM with the same IP, one in terminating states, , time_elapsed < threshold
        #   no start_vm_termination, no remove_vm_from_pool
        mc_time.time.return_value = 1
        self.vmd_a2.store_field(self.rc, "vm_ip", self.vmd_a1.vm_ip)

        self.vm_master.terminate_again()
        assert not self.vmm.remove_vm_from_pool.called
        assert not self.vmm.start_vm_termination.called

        # case 4: two VM with the same IP, one in terminating states, , time_elapsed > threshold
        #   no start_vm_termination, remove_vm_from_pool
        mc_time.time.return_value = 1 + self.opts.build_groups[0]["vm_terminating_timeout"]
        self.vm_master.terminate_again()
        assert self.vmm.remove_vm_from_pool.called
        assert self.vmm.remove_vm_from_pool.call_args[0][0] == self.vmd_a1.vm_name
        assert not self.vmm.start_vm_termination.called

    # def test_run_undefined_helpers(self, mc_setproctitle):
    #     for target in ["spawner", "terminator", "checker"]:
    #         setattr(self.vmm, target, None)
    #         with pytest.raises(RuntimeError):
    #             self.vm_master.run()
    #
    #         setattr(self.vmm, target, MagicMock())
    #
    #         assert not mc_setproctitle.called

    def test_dummy_run(self, mc_time, mc_setproctitle):
        mc_do_cycle = MagicMock()
        mc_do_cycle.side_effect = [
            VmError("FooBar"),
            None
        ]
        self.vm_master.do_cycle = types.MethodType(mc_do_cycle, self.vm_master)
        self.vmm.mark_server_start = MagicMock()

        self.stage = 0

        def on_sleep(*args, **kwargs):
            self.stage += 1
            if self.stage == 1:
                pass
            elif self.stage >= 2:
                self.vm_master.kill_received = True

        mc_time.sleep.side_effect = on_sleep
        self.vm_master.run()

    def test_dummy_terminate(self):
        self.vm_master.terminate()
        assert self.vm_master.kill_received
        assert self.vm_master.checker.terminate.called
        assert self.vm_master.spawner.terminate.called

    def test_dummy_do_cycle(self):
        self.vm_master.remove_old_dirty_vms = types.MethodType(MagicMock(), self.vm_master)
        self.vm_master.check_vms_health = types.MethodType(MagicMock(), self.vm_master)
        self.vm_master.start_spawn_if_required = types.MethodType(MagicMock(), self.vm_master)
        # self.vm_master.remove_old_dirty_vms = types(MagicMock, self.vm_master)

        self.vm_master.do_cycle()

        assert self.vm_master.remove_old_dirty_vms.called
        assert self.vm_master.check_vms_health.called
        assert self.vm_master.start_spawn_if_required.called
        assert self.vm_master.spawner.recycle.called

    def test_dummy_start_spawn_if_required(self):
        self.vm_master.try_spawn_one = MagicMock()
        self.vm_master.start_spawn_if_required()
        assert self.vm_master.try_spawn_one.call_args_list == [
            mock.call(group) for group in range(self.opts.build_groups_count)
        ]

    def test__check_total_running_vm_limit_raises(self):
        self.vm_master.log = MagicMock()
        active_vm_states = [VmStates.GOT_IP, VmStates.READY, VmStates.IN_USE, VmStates.CHECK_HEALTH]
        cases = [
            # active_vms_number , spawn_procs_number
            (x, 11 - x) for x in range(12)
        ]
        self.opts.build_groups[0]["max_vm_total"] = 11
        for active_vms_number, spawn_procs_number in cases:
            vmd_list = [
                self.vmm.add_vm_to_pool("127.0.0.{}".format(idx + 1), "a{}".format(idx), 0)
                for idx in range(active_vms_number)
            ]
            for idx in range(active_vms_number):
                state = choice(active_vm_states)
                vmd_list[idx].store_field(self.rc, "state", state)

            self.vm_master.spawner.get_proc_num_per_group.return_value = spawn_procs_number
            with pytest.raises(VmSpawnLimitReached):
                self.vm_master._check_total_running_vm_limit(0)
            self.vm_master.log.reset_mock()

            # teardown
            self.clean_redis()

    def test__check_total_running_vm_limit_ok(self):
        self.vm_master.log = MagicMock()
        active_vm_states = [VmStates.GOT_IP, VmStates.READY, VmStates.IN_USE, VmStates.CHECK_HEALTH]
        cases = [
            # active_vms_number , spawn_procs_number
            (x, 11 - x) for x in range(12)
        ]
        self.opts.build_groups[0]["max_vm_total"] = 12
        for active_vms_number, spawn_procs_number in cases:
            vmd_list = [
                self.vmm.add_vm_to_pool("127.0.0.{}".format(idx + 1), "a{}".format(idx), 0)
                for idx in range(active_vms_number)
            ]
            for idx in range(active_vms_number):
                state = choice(active_vm_states)
                vmd_list[idx].store_field(self.rc, "state", state)
            # self.vmm.spawner.children_number = spawn_procs_number
            self.vm_master.spawner.get_proc_num_per_group.return_value = spawn_procs_number

            # doesn't raise exception
            self.vm_master._check_total_running_vm_limit(0)
            self.vm_master.log.reset_mock()

            # teardown
            self.clean_redis()

    def test__check_elapsed_time_after_spawn(self, mc_time):
        # don't start new spawn if last_spawn_time was in less self.vm_spawn_min_interval ago
        mc_time.time.return_value = 0
        self.vm_master._check_elapsed_time_after_spawn(0)

        self.vm_master.vmm.write_vm_pool_info(0, "last_vm_spawn_start", 0)
        with pytest.raises(VmSpawnLimitReached):
            self.vm_master._check_elapsed_time_after_spawn(0)

        mc_time.time.return_value = -1 + self.vm_spawn_min_interval
        with pytest.raises(VmSpawnLimitReached):
            self.vm_master._check_elapsed_time_after_spawn(0)

        mc_time.time.return_value = 1 + self.vm_spawn_min_interval
        self.vm_master._check_elapsed_time_after_spawn(0)
        # we don't care about other group
        self.vm_master.vmm.write_vm_pool_info(1, "last_vm_spawn_start", mc_time.time.return_value)
        self.vm_master._check_elapsed_time_after_spawn(0)
        with pytest.raises(VmSpawnLimitReached):
            self.vm_master._check_elapsed_time_after_spawn(1)

    def test__check_number_of_running_spawn_processes(self):
        for i in range(self.opts.build_groups[0]["max_spawn_processes"]):
            self.vm_master.spawner.get_proc_num_per_group.return_value = i
            self.vm_master._check_number_of_running_spawn_processes(0)

        for i in [0, 1, 2, 5, 100]:
            self.vm_master.spawner.get_proc_num_per_group.return_value = \
                self.opts.build_groups[0]["max_spawn_processes"] + i

            with pytest.raises(VmSpawnLimitReached):
                self.vm_master._check_number_of_running_spawn_processes(0)

    def test__check_total_vm_limit(self):
        self.vm_master.vmm = MagicMock()
        for i in range(2 * self.opts.build_groups[0]["max_vm_total"]):
            self.vm_master.vmm.get_all_vm_in_group.return_value = [1 for _ in range(i)]
            self.vm_master._check_total_vm_limit(0)

        for i in range(2 * self.opts.build_groups[0]["max_vm_total"],
                       2 * self.opts.build_groups[0]["max_vm_total"] + 10):
            self.vm_master.vmm.get_all_vm_in_group.return_value = [1 for _ in range(i)]
            with pytest.raises(VmSpawnLimitReached):
                self.vm_master._check_total_vm_limit(0)

    @skip("Fixme or remove, test doesn't work.")
    def test_try_spawn_error_handling(self, mc_time):
        mc_time.time.return_value = 0
        self.vm_master.log = MagicMock()

        self.vm_master.spawner.start_spawn.side_effect = IOError()

        self.vm_master.try_spawn_one(0)
        assert self.vm_master.spawner.start_spawn.called

    def test_try_spawn_exit_on_check_fail(self):
        check_mocks = []
        for check_name in [
            "_check_total_running_vm_limit",
            "_check_elapsed_time_after_spawn",
            "_check_number_of_running_spawn_processes",
            "_check_total_vm_limit",
        ]:
            mc_check_func = MagicMock()
            check_mocks.append(mc_check_func)
            setattr(self.vm_master, check_name, mc_check_func)

        self.vm_master.vmm = MagicMock()
        for idx in range(len(check_mocks)):
            for cm in check_mocks:
                cm.side_effect = None
            check_mocks[idx].side_effect = VmSpawnLimitReached("test")

            self.vm_master.try_spawn_one(0)
            assert not self.vm_master.vmm.write_vm_pool_info.called
            self.vm_master.vmm.write_vm_pool_info.reset_mock()

        for cm in check_mocks:
            cm.side_effect = None

        self.vm_master.try_spawn_one(0)
        assert self.vm_master.vmm.write_vm_pool_info.called
        assert self.vm_master.spawner.start_spawn.called

    def test_start_vm_check_ok_ok(self):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)
        # can start, no problem to start
        # > can start IN_USE, don't change status
        vmd.store_field(self.rc, "state", VmStates.IN_USE)
        self.vm_master.start_vm_check(vm_name=self.vm_name)

        assert self.checker.run_check_health.called
        self.checker.run_check_health.reset_mock()
        assert vmd.get_field(self.rc, "state") == VmStates.IN_USE

        # > changes status to HEALTH_CHECK
        states = [VmStates.GOT_IP, VmStates.CHECK_HEALTH_FAILED, VmStates.READY]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            self.vm_master.start_vm_check(vm_name=self.vm_name)

            assert self.checker.run_check_health.called
            self.checker.run_check_health.reset_mock()
            assert vmd.get_field(self.rc, "state") == VmStates.CHECK_HEALTH

    def test_start_vm_check_wrong_old_state(self):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)

        states = [VmStates.TERMINATING, VmStates.CHECK_HEALTH]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            assert not self.vm_master.start_vm_check(vm_name=self.vm_name)

            assert not self.checker.run_check_health.called
            assert vmd.get_field(self.rc, "state") == state

    def test_start_vm_check_lua_ok_check_spawn_failed(self):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)

        self.vm_master.checker.run_check_health.side_effect = RuntimeError()

        # restore orig state
        states = [VmStates.GOT_IP, VmStates.CHECK_HEALTH_FAILED, VmStates.READY, VmStates.IN_USE]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            self.vm_master.start_vm_check(vm_name=self.vm_name)

            assert self.checker.run_check_health.called
            self.checker.run_check_health.reset_mock()
            assert vmd.get_field(self.rc, "state") == state
