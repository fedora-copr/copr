# coding: utf-8
import json

import types
import time
from multiprocessing import Queue

from bunch import Bunch
import six

from backend import exceptions
from backend.exceptions import VmError, NoVmAvailable
from backend.vm_manage import VmStates, KEY_VM_POOL, PUBSUB_VM_TERMINATION, PUBSUB_MB, EventTopics
from backend.vm_manage.manager import VmManager
from backend.daemons.vm_master import VmMaster
from backend.helpers import get_redis_connection


if six.PY3:
    from unittest import mock
else:
    import mock
    from mock import MagicMock

import pytest


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "backend.vm_manage.manager"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


class TestCallback(object):
    def log(self, msg):
        print(msg)


class TestManager(object):

    def setup_method(self, method):
        self.opts = Bunch(
            redis_db=9,
            ssh=Bunch(
                transport="ssh"
            ),
            build_groups_count=1,
            build_groups={
                0: {
                    "name": "base",
                    "archs": ["i386", "x86_64"]
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            # worker_logdir=self.,
            timeout=1800,
            # destdir=self.tmp_dir_path,
            results_baseurl="/tmp",
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

        self.queue = Queue()
        self.vmm = VmManager(self.opts, self.queue,
                             checker=self.checker,
                             spawner=self.spawner,
                             terminator=self.terminator)
        self.vmm.post_init()
        self.vmm.log = MagicMock()
        self.pid = 12345

    def teardown_method(self, method):
        keys = self.vmm.rc.keys("*")
        if keys:
            self.vmm.rc.delete(*keys)

    @pytest.fixture
    def f_second_group(self):
        self.opts.build_groups_count = 2
        self.opts.build_groups[1] = {
            "name": "arm",
            "archs": ["armV7",]
        }

    def test_add_vm_to_pool(self):
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)

        vm_list = self.vmm.get_all_vm_in_group(self.group)

        vm = self.vmm.get_vm_by_name(self.vm_name)
        assert len(vm_list) == 1
        assert vm_list[0].__dict__ == vm.__dict__
        assert self.group in self.vmm.vm_groups
        assert len(self.vmm.vm_groups) == 1

        with pytest.raises(VmError):
            self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)

    def test_start_vm_check_ok_ok(self):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)
        # can start, no problem to start
        # > can start IN_USE, don't change status
        vmd.store_field(self.rc, "state", VmStates.IN_USE)
        self.vmm.start_vm_check(vm_name=self.vm_name)

        assert self.checker.run_check_health.called
        self.checker.run_check_health.reset_mock()
        assert vmd.get_field(self.rc, "state") == VmStates.IN_USE

        # > changes status to HEALTH_CHECK
        states = [VmStates.GOT_IP, VmStates.CHECK_HEALTH_FAILED, VmStates.READY]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            self.vmm.start_vm_check(vm_name=self.vm_name)

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
            assert not self.vmm.start_vm_check(vm_name=self.vm_name)

            assert not self.checker.run_check_health.called
            assert vmd.get_field(self.rc, "state") == state

    def test_mark_vm_check_failed(self, mc_time):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)
        vmd.store_field(self.rc, "state", VmStates.CHECK_HEALTH)
        vmd.store_field(self.rc, "last_health_check", 12345)

        self.vmm.mark_vm_check_failed(self.vm_name)

        assert vmd.get_field(self.rc, "state") == VmStates.CHECK_HEALTH_FAILED
        states = [VmStates.GOT_IP, VmStates.IN_USE, VmStates.READY, VmStates.TERMINATING]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            self.vmm.mark_vm_check_failed(self.vm_name)
            assert vmd.get_field(self.rc, "state") == state

    def test_start_vm_check_lua_ok_check_spawn_failed(self):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd = self.vmm.get_vm_by_name(self.vm_name)

        self.vmm.checker.run_check_health.side_effect = RuntimeError()

        # restore orig state
        states = [VmStates.GOT_IP, VmStates.CHECK_HEALTH_FAILED, VmStates.READY, VmStates.IN_USE]
        for state in states:
            vmd.store_field(self.rc, "state", state)
            self.vmm.start_vm_check(vm_name=self.vm_name)

            assert self.checker.run_check_health.called
            self.checker.run_check_health.reset_mock()
            assert vmd.get_field(self.rc, "state") == state

    def test_acquire_vm_extra_kwargs(self):
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd.store_field(self.rc, "state", VmStates.READY)

        kwargs = {
            "task_id": "20-fedora-20-x86_64",
            "build_id": "20",
            "chroot": "fedora-20-x86_64"
        }
        vmd_got = self.vmm.acquire_vm(self.group, self.username, self.pid, **kwargs)
        for k, v in kwargs.items():
            assert vmd_got.get_field(self.rc, k) == v

    def test_acquire_vm(self):
        vmd_main = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd_alt = self.vmm.add_vm_to_pool(self.vm_ip, "alternative", self.group)

        vmd_main.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.vmm.rc, "bound_to_user", self.username)

        vmd_got_first = self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)
        assert vmd_got_first.vm_name == "alternative"
        vmd_got_second = self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)
        assert vmd_got_second.vm_name == self.vm_name

        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)

    def test_acquire_only_ready_state(self):
        vmd_main = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)

        for state in [VmStates.IN_USE, VmStates.GOT_IP, VmStates.CHECK_HEALTH,
                      VmStates.TERMINATING, VmStates.CHECK_HEALTH_FAILED]:
            vmd_main.store_field(self.rc, "state", state)
            with pytest.raises(NoVmAvailable):
                self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)

    def test_acquire_and_release_vm(self):
        vmd_main = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd_alt = self.vmm.add_vm_to_pool(self.vm_ip, "alternative", self.group)

        vmd_main.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.vmm.rc, "bound_to_user", self.username)

        vmd_got_first = self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)
        assert vmd_got_first.vm_name == "alternative"

        self.vmm.release_vm("alternative")
        vmd_got_again = self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)
        assert vmd_got_again.vm_name == "alternative"

        vmd_got_another = self.vmm.acquire_vm(group=self.group, username=self.username, pid=self.pid)
        assert vmd_got_another.vm_name == self.vm_name

    def test_release_only_in_use(self):
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)

        for state in [VmStates.READY, VmStates.GOT_IP, VmStates.CHECK_HEALTH,
                      VmStates.TERMINATING, VmStates.CHECK_HEALTH_FAILED]:
            vmd.store_field(self.rc, "state", state)

            assert not self.vmm.release_vm(self.vm_name)

    def rcv_from_ps_message_bus(self):
        # don't forget to subscribe self.ps
        rcv_msg_list = []
        for i in range(10):
            msg = self.ps.get_message()
            if msg:
                rcv_msg_list.append(msg)
            time.sleep(0.01)
        return rcv_msg_list

    def test_start_vm_termination(self):
        self.ps = self.vmm.rc.pubsub(ignore_subscribe_messages=True)
        self.ps.subscribe(PUBSUB_MB)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)

        self.vmm.start_vm_termination(self.vm_name)
        rcv_msg_list = self.rcv_from_ps_message_bus()
        # print(rcv_msg_list)
        assert len(rcv_msg_list) == 1
        msg = rcv_msg_list[0]
        assert msg["type"] == "message"
        data = json.loads(msg["data"])
        assert data["topic"] == EventTopics.VM_TERMINATION_REQUEST
        assert data["vm_name"] == self.vm_name

    def test_start_vm_termination_2(self):
        self.ps = self.vmm.rc.pubsub(ignore_subscribe_messages=True)
        self.ps.subscribe(PUBSUB_MB)

        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd.store_field(self.rc, "state", VmStates.TERMINATING)
        self.vmm.start_vm_termination(self.vm_name, allowed_pre_state=VmStates.TERMINATING)
        rcv_msg_list = self.rcv_from_ps_message_bus()
        # print(rcv_msg_list)
        assert len(rcv_msg_list) == 1
        msg = rcv_msg_list[0]
        assert msg["type"] == "message"
        data = json.loads(msg["data"])
        assert data["topic"] == EventTopics.VM_TERMINATION_REQUEST
        assert data["vm_name"] == self.vm_name

    def test_start_vm_termination_fail(self):
        self.ps = self.vmm.rc.pubsub(ignore_subscribe_messages=True)
        self.ps.subscribe(PUBSUB_MB)
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        vmd.store_field(self.rc, "state", VmStates.TERMINATING)

        self.vmm.start_vm_termination(self.vm_name)
        rcv_msg_list = self.rcv_from_ps_message_bus()
        assert len(rcv_msg_list) == 0

        vmd.store_field(self.rc, "state", VmStates.READY)
        self.vmm.start_vm_termination(self.vm_name, allowed_pre_state=VmStates.IN_USE)
        rcv_msg_list = self.rcv_from_ps_message_bus()
        assert len(rcv_msg_list) == 0
        assert vmd.get_field(self.rc, "state") == VmStates.READY

        vmd.store_field(self.rc, "state", VmStates.TERMINATING)
        self.vmm.start_vm_termination(self.vm_name)
        rcv_msg_list = self.rcv_from_ps_message_bus()
        assert len(rcv_msg_list) == 0
        assert vmd.get_field(self.rc, "state") == VmStates.TERMINATING

    def test_remove_vm_from_pool_only_terminated(self):
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, self.group)
        for state in [VmStates.IN_USE, VmStates.GOT_IP, VmStates.CHECK_HEALTH,
                      VmStates.READY, VmStates.CHECK_HEALTH_FAILED]:

            vmd.store_field(self.vmm.rc, "state", state)
            with pytest.raises(VmError):
                self.vmm.remove_vm_from_pool(self.vm_name)

        vmd.store_field(self.vmm.rc, "state", VmStates.TERMINATING)
        self.vmm.remove_vm_from_pool(self.vm_name)
        assert self.vmm.rc.scard(KEY_VM_POOL.format(group=self.group)) == 0

    def test_get_vms(self, f_second_group, capsys):
        vmd_1 = self.vmm.add_vm_to_pool(self.vm_ip, "a1", self.group)
        vmd_2 = self.vmm.add_vm_to_pool(self.vm_ip, "a2", self.group)
        vmd_3 = self.vmm.add_vm_to_pool(self.vm_ip, "b1", 1)
        vmd_4 = self.vmm.add_vm_to_pool(self.vm_ip, "b2", 1)
        vmd_5 = self.vmm.add_vm_to_pool(self.vm_ip, "b3", 1)

        assert set(v.vm_name for v in self.vmm.get_all_vm_in_group(0)) == set(["a1", "a2"])
        assert set(v.vm_name for v in self.vmm.get_all_vm_in_group(1)) == set(["b1", "b2", "b3"])

        assert set(v.vm_name for v in self.vmm.get_all_vm()) == set(["a1", "a2", "b1", "b2", "b3"])

        vmd_1.store_field(self.rc, "state", VmStates.GOT_IP)
        vmd_2.store_field(self.rc, "state", VmStates.GOT_IP)
        vmd_3.store_field(self.rc, "state", VmStates.GOT_IP)
        vmd_4.store_field(self.rc, "state", VmStates.READY)
        vmd_5.store_field(self.rc, "state", VmStates.IN_USE)

        vmd_list = self.vmm.get_vm_by_group_and_state_list(group=None, state_list=[VmStates.GOT_IP, VmStates.IN_USE])
        assert set(v.vm_name for v in vmd_list) == set(["a1", "a2", "b1", "b3"])
        vmd_list = self.vmm.get_vm_by_group_and_state_list(group=1, state_list=[VmStates.READY])
        assert set(v.vm_name for v in vmd_list) == set(["b2"])

        self.vmm.info()

    def test_look_up_vms_by_ip(self, f_second_group, capsys):
        vmd_1 = self.vmm.add_vm_to_pool(self.vm_ip, "a1", self.group)
        r1 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r1) == 1
        assert r1[0].vm_name == "a1"

        vmd_2 = self.vmm.add_vm_to_pool(self.vm_ip, "a2", self.group)
        r2 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r2) == 2
        r2 = sorted(r2, key=lambda vmd: vmd.vm_name)
        assert r2[0].vm_name == "a1"
        assert r2[1].vm_name == "a2"

        vmd_3 = self.vmm.add_vm_to_pool("127.1.1.111", "b1", 1)

        r3 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r3) == 2
        r3 = sorted(r3, key=lambda vmd: vmd.vm_name)
        assert r3[0].vm_name == "a1"
        assert r3[1].vm_name == "a2"
