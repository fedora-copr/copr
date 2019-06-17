# coding: utf-8
import json
import random

import types
import time
from multiprocessing import Queue

from munch import Munch

from backend import exceptions
from backend.exceptions import VmError, NoVmAvailable
from backend.vm_manage import VmStates, KEY_VM_POOL, PUBSUB_MB, EventTopics, KEY_SERVER_INFO
from backend.vm_manage.manager import VmManager
from backend.daemons.vm_master import VmMaster
from backend.helpers import get_redis_connection

from  unittest import mock
from unittest.mock import MagicMock
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

GID1 = 0
GID2 = 1

# some sandbox string, for tests where we don't care about its value
SANDBOX = 'sandbox'

class TestManager(object):

    def setup_method(self, method):
        self.opts = Munch(
            redis_db=9,
            redis_port=7777,
            ssh=Munch(
                transport="ssh"
            ),
            build_groups_count=2,
            build_groups={
                GID1: {
                    "name": "base",
                    "archs": ["i386", "x86_64"],
                    "max_vm_per_user": 3,
                },
                GID2: {
                    "name": "arm",
                    "archs": ["armV7",]
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            timeout=1800,
            # destdir=self.tmp_dir_path,
            results_baseurl="/tmp",
        )

        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"

        self.vm2_ip = "127.0.0.2"
        self.vm2_name = "localhost2"

        self.ownername = "bob"

        self.rc = get_redis_connection(self.opts)
        self.ps = None
        self.log_msg_list = []

        self.vmm = VmManager(self.opts)
        self.vmm.log = MagicMock()
        self.pid = 12345

    def teardown_method(self, method):
        keys = self.vmm.rc.keys("*")
        if keys:
            self.vmm.rc.delete(*keys)

    def test_manager_setup(self):
        vmm = VmManager(self.opts)
        assert GID1 in vmm.vm_groups
        assert GID2 in vmm.vm_groups
        assert len(vmm.vm_groups) == 2

    def test_add_vm_to_pool(self):
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)

        with pytest.raises(VmError):
            self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)

        vm_list = self.vmm.get_all_vm_in_group(GID1)
        vm = self.vmm.get_vm_by_name(self.vm_name)

        assert len(vm_list) == 1
        assert vm_list[0].__dict__ == vm.__dict__
        assert vm.vm_ip == self.vm_ip
        assert vm.vm_name == self.vm_name
        assert vm.group == GID1

    def test_mark_vm_check_failed(self, mc_time):
        self.vmm.start_vm_termination = types.MethodType(MagicMock(), self.vmm)
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
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

    def test_acquire_vm_no_vm_after_server_restart(self, mc_time):
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd.store_field(self.rc, "state", VmStates.READY)

        # undefined both last_health_check and server_start_timestamp
        mc_time.time.return_value = 0.1
        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)

        # only server start timestamp is defined
        mc_time.time.return_value = 1
        self.vmm.mark_server_start()
        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)

        # only last_health_check defined
        self.rc.delete(KEY_SERVER_INFO)
        vmd.store_field(self.rc, "last_health_check", 0)
        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)

        # both defined but last_health_check < server_start_time
        self.vmm.mark_server_start()
        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)

        # and finally last_health_check > server_start_time
        vmd.store_field(self.rc, "last_health_check", 2)
        vmd_res = self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)
        assert vmd.vm_name == vmd_res.vm_name

    def test_acquire_vm_extra_kwargs(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd.store_field(self.rc, "state", VmStates.READY)
        vmd.store_field(self.rc, "last_health_check", 2)

        kwargs = {
            "task_id": "20-fedora-20-x86_64",
            "build_id": "20",
            "chroot": "fedora-20-x86_64"
        }
        vmd_got = self.vmm.acquire_vm([GID1], self.ownername, self.pid,
                                      SANDBOX, **kwargs)
        for k, v in kwargs.items():
            assert vmd_got.get_field(self.rc, k) == v

    def test_another_owner_cannot_acquire_vm(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd.store_field(self.rc, "state", VmStates.READY)
        vmd.store_field(self.rc, "last_health_check", 2)
        vmd.store_field(self.vmm.rc, "bound_to_user", "foo")
        vmd.store_field(self.vmm.rc, "sandbox", SANDBOX)
        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm(groups=[GID1], ownername=self.ownername,
                    pid=self.pid, sandbox=SANDBOX)
        vm = self.vmm.acquire_vm(groups=[GID1], ownername="foo", pid=self.pid,
                                 sandbox=SANDBOX)
        assert vm.vm_name == self.vm_name

    def test_different_sandbox_cannot_acquire_vm(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd.store_field(self.rc, "state", VmStates.READY)
        vmd.store_field(self.rc, "last_health_check", 2)
        vmd.store_field(self.vmm.rc, "bound_to_user", "foo")
        vmd.store_field(self.vmm.rc, "sandbox", "sandboxA")

        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm(groups=[GID1], ownername="foo",
                    pid=self.pid, sandbox="sandboxB")
        vm = self.vmm.acquire_vm(groups=[GID1], ownername="foo", pid=self.pid,
                                 sandbox="sandboxA")
        assert vm.vm_name == self.vm_name

    def test_acquire_vm(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()

        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd_alt = self.vmm.add_vm_to_pool(self.vm_ip, "vm_alt", GID1)
        vmd2 = self.vmm.add_vm_to_pool(self.vm2_ip, self.vm2_name, GID2)

        vmd.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.rc, "state", VmStates.READY)
        vmd2.store_field(self.rc, "state", VmStates.READY)

        vmd.store_field(self.rc, "last_health_check", 2)
        vmd_alt.store_field(self.rc, "last_health_check", 2)
        vmd2.store_field(self.rc, "last_health_check", 2)

        vmd_alt.store_field(self.vmm.rc, "bound_to_user", self.ownername)
        vmd_alt.store_field(self.vmm.rc, "sandbox", SANDBOX)

        vmd_got_first = self.vmm.acquire_vm([GID1, GID2],
                ownername=self.ownername, pid=self.pid, sandbox=SANDBOX)
        assert vmd_got_first.vm_name == "vm_alt"

        vmd_got_second = self.vmm.acquire_vm([GID1, GID2],
                ownername=self.ownername, pid=self.pid, sandbox=SANDBOX)
        assert vmd_got_second.vm_name == self.vm_name

        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm(groups=[GID1], ownername=self.ownername,
                    pid=self.pid, sandbox=SANDBOX)

        vmd_got_third = self.vmm.acquire_vm(groups=[GID1, GID2],
                ownername=self.ownername, pid=self.pid, sandbox=SANDBOX)
        assert vmd_got_third.vm_name == self.vm2_name

    def test_acquire_vm_per_user_limit(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()
        max_vm_per_user = self.opts.build_groups[GID1]["max_vm_per_user"]

        vmd_list = []
        for idx in range(max_vm_per_user + 1):
            vmd = self.vmm.add_vm_to_pool("127.0.{}.1".format(idx), "vm_{}".format(idx), GID1)
            vmd.store_field(self.rc, "state", VmStates.READY)
            vmd.store_field(self.rc, "last_health_check", 2)
            vmd_list.append(vmd)

        for idx in range(max_vm_per_user):
            self.vmm.acquire_vm([GID1], self.ownername, idx, SANDBOX)

        with pytest.raises(NoVmAvailable):
            self.vmm.acquire_vm([GID1], self.ownername, 42, SANDBOX)

    def test_acquire_only_ready_state(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()

        vmd_main = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd_main.store_field(self.rc, "last_health_check", 2)

        for state in [VmStates.IN_USE, VmStates.GOT_IP, VmStates.CHECK_HEALTH,
                      VmStates.TERMINATING, VmStates.CHECK_HEALTH_FAILED]:
            vmd_main.store_field(self.rc, "state", state)
            with pytest.raises(NoVmAvailable):
                self.vmm.acquire_vm(groups=[GID1], ownername=self.ownername,
                                    pid=self.pid, sandbox=SANDBOX)

    def test_acquire_and_release_vm(self, mc_time):
        mc_time.time.return_value = 0
        self.vmm.mark_server_start()

        vmd_main = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        vmd_alt = self.vmm.add_vm_to_pool(self.vm_ip, "vm_alt", GID1)

        vmd_main.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.rc, "state", VmStates.READY)
        vmd_alt.store_field(self.vmm.rc, "bound_to_user", self.ownername)
        vmd_alt.store_field(self.vmm.rc, "sandbox", SANDBOX)
        vmd_main.store_field(self.rc, "last_health_check", 2)
        vmd_alt.store_field(self.rc, "last_health_check", 2)

        vmd_got_first = self.vmm.acquire_vm(
            groups=[GID1], ownername=self.ownername, pid=self.pid,
            sandbox=SANDBOX)
        assert vmd_got_first.vm_name == "vm_alt"

        self.vmm.release_vm("vm_alt")
        vmd_got_again = self.vmm.acquire_vm(
            groups=[GID1], ownername=self.ownername, pid=self.pid,
            sandbox=SANDBOX)
        assert vmd_got_again.vm_name == "vm_alt"

        vmd_got_another = self.vmm.acquire_vm(
            groups=[GID1], ownername=self.ownername, pid=self.pid,
            sandbox=SANDBOX)
        assert vmd_got_another.vm_name == self.vm_name

    def test_release_only_in_use(self):
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)

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
        self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)

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

        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
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
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
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
        vmd = self.vmm.add_vm_to_pool(self.vm_ip, self.vm_name, GID1)
        for state in [VmStates.IN_USE, VmStates.GOT_IP, VmStates.CHECK_HEALTH,
                      VmStates.READY, VmStates.CHECK_HEALTH_FAILED]:

            vmd.store_field(self.vmm.rc, "state", state)
            with pytest.raises(VmError):
                self.vmm.remove_vm_from_pool(self.vm_name)

        vmd.store_field(self.vmm.rc, "state", VmStates.TERMINATING)
        self.vmm.remove_vm_from_pool(self.vm_name)
        assert self.vmm.rc.scard(KEY_VM_POOL.format(group=GID1)) == 0

    def test_get_vms(self, capsys):
        vmd_1 = self.vmm.add_vm_to_pool(self.vm_ip, "a1", GID1)
        vmd_2 = self.vmm.add_vm_to_pool(self.vm_ip, "a2", GID1)
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

    def test_look_up_vms_by_ip(self, capsys):
        self.vmm.add_vm_to_pool(self.vm_ip, "a1", GID1)
        r1 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r1) == 1
        assert r1[0].vm_name == "a1"

        self.vmm.add_vm_to_pool(self.vm_ip, "a2", GID1)
        r2 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r2) == 2
        r2 = sorted(r2, key=lambda vmd: vmd.vm_name)
        assert r2[0].vm_name == "a1"
        assert r2[1].vm_name == "a2"

        self.vmm.add_vm_to_pool("127.1.1.111", "b1", 1)

        r3 = self.vmm.lookup_vms_by_ip(self.vm_ip)
        assert len(r3) == 2
        r3 = sorted(r3, key=lambda vmd: vmd.vm_name)
        assert r3[0].vm_name == "a1"
        assert r3[1].vm_name == "a2"

    def test_mark_server_start(self, mc_time):
        assert self.rc.hget(KEY_SERVER_INFO, "server_start_timestamp") is None
        for i in range(100):
            val = 100 * i + 0.12345
            mc_time.time.return_value = val
            self.vmm.mark_server_start()
            assert self.rc.hget(KEY_SERVER_INFO, "server_start_timestamp") == "{}".format(val)
