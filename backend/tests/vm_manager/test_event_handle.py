# coding: utf-8
import json
import shutil
import tempfile
import time
from multiprocessing import Queue
import types

from munch import Munch
from redis.client import Script

from backend.exceptions import VmDescriptorNotFound
from backend.helpers import get_redis_connection
from backend.vm_manage import VmStates
from backend.vm_manage.event_handle import EventHandler, Recycle
from backend.vm_manage.models import VmDescriptor

from unittest import mock
from unittest.mock import MagicMock
import pytest


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "backend.vm_manage.event_handle"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_setproctitle():
    with mock.patch("{}.setproctitle".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_process():
    with mock.patch("{}.Process".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_recycle():
    with mock.patch("{}.Recycle".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_run_ans():
    with mock.patch("{}.run_ansible_playbook_once".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_grc():
    with mock.patch("{}.get_redis_connection".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_grl():
    with mock.patch("{}.get_redis_logger".format(MODULE_REF)) as handle:
        yield handle


class TestEventHandle(object):

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.terminate_pb_path = "{}/terminate.yml".format(self.test_root_path)
        self.opts = Munch(
            redis_db=9,
            redis_port=7777,
            ssh=Munch(
                transport="ssh"
            ),
            build_groups={
                0: {
                    "terminate_playbook": self.terminate_pb_path,
                    "name": "base",
                    "archs": ["i386", "x86_64"],
                    "vm_max_check_fails": 2,
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            timeout=1800,
            # destdir=self.tmp_dir_path,
            results_baseurl="/tmp",
        )
        self.rc = get_redis_connection(self.opts)

        self.checker = MagicMock()
        self.spawner = MagicMock()
        self.terminator = MagicMock()

        self.queue = Queue()
        self.vmm = MagicMock()
        self.vmm.rc = self.rc

        self.grl_patcher = mock.patch("{}.get_redis_logger".format(MODULE_REF))
        self.grl_patcher.start()

        self.eh = EventHandler(self.opts,
                               self.vmm,
                               self.terminator)
        self.eh.post_init()

        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"
        self.group = 0
        self.username = "bob"

        self.msg = {"vm_ip": self.vm_ip, "vm_name": self.vm_name, "group": self.group}
        self.stage = 0

    def erase_redis(self):
        keys = self.rc.keys("*")
        if keys:
            self.rc.delete(*keys)

    def teardown_method(self, method):
        self.grl_patcher.stop()
        shutil.rmtree(self.test_root_path)
        self.erase_redis()

    def test_post_init(self):
        test_eh = EventHandler(self.opts, self.vmm, self.terminator)
        assert "on_health_check_success" not in test_eh.lua_scripts
        test_eh.post_init()
        assert test_eh.lua_scripts["on_health_check_success"]
        assert isinstance(test_eh.lua_scripts["on_health_check_success"], Script)

    def test_recycle(self, mc_time):
        self.recycle = Recycle(terminator=self.terminator, recycle_period=60)
        self.stage = 0

        def incr(*args, **kwargs):
            self.stage += 1
            if self.stage > 2:
                self.recycle.terminate()
        mc_time.sleep.side_effect = incr

        assert not self.terminator.recycle.called
        self.recycle.run()
        assert self.terminator.recycle.called
        assert len(self.terminator.recycle.call_args_list) == 3

    def test_on_vm_spawned(self):
        expected_call = mock.call(**self.msg)
        self.eh.on_vm_spawned(self.msg)
        assert self.vmm.add_vm_to_pool.call_args == expected_call

    def test_on_vm_termination_request(self):
        expected_call = mock.call(**self.msg)
        self.eh.on_vm_termination_request(self.msg)
        assert self.terminator.terminate_vm.call_args == expected_call

    def test_health_check_result_no_vmd(self):
        self.vmm.get_vm_by_name.side_effect = VmDescriptorNotFound("foobar")
        self.eh.lua_scripts = MagicMock()

        self.eh.on_health_check_result(self.msg)
        assert not self.eh.lua_scripts["on_health_check_success"].called

    def test_health_check_result_on_ok(self):
        # on success should change state from "check_health" to "ready"
        # and reset check fails to zero
        self.vmd = VmDescriptor(self.vm_ip, self.vm_name, self.group, VmStates.CHECK_HEALTH)
        self.vmd.store(self.rc)
        self.vmd.store_field(self.rc, "check_fails", 1)

        self.vmm.get_vm_by_name.return_value = self.vmd
        msg = self.msg
        msg["result"] = "OK"

        self.eh.on_health_check_result(msg)
        assert self.vmd.get_field(self.rc, "state") == VmStates.READY
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 0

        # if old state in "in_use" don't change it
        self.vmd.store_field(self.rc, "state", VmStates.IN_USE)
        self.vmd.store_field(self.rc, "check_fails", 1)
        self.eh.on_health_check_result(msg)

        assert self.vmd.get_field(self.rc, "state") == VmStates.IN_USE
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 0

        # if old state not in ["in_use", "check_health"] don't touch it
        # and also don't reset check_fails
        self.vmd.store_field(self.rc, "check_fails", 1)
        for state in [VmStates.TERMINATING, VmStates.GOT_IP, VmStates.READY]:
            self.vmd.store_field(self.rc, "state", state)
            self.eh.on_health_check_result(msg)

            assert int(self.vmd.get_field(self.rc, "check_fails")) == 1
            assert self.vmd.get_field(self.rc, "state") == state

    def test_health_check_result_on_fail_from_check_health(self):
        # on fail set state to check failed state and increment fails counter
        self.vmd = VmDescriptor(self.vm_ip, self.vm_name, self.group, VmStates.CHECK_HEALTH)
        self.vmd.store(self.rc)

        self.vmm.get_vm_by_name.return_value = self.vmd
        msg = self.msg
        msg["result"] = "failed"

        assert self.vmd.get_field(self.rc, "state") == VmStates.CHECK_HEALTH
        self.eh.on_health_check_result(msg)
        assert self.vmd.get_field(self.rc, "state") == VmStates.CHECK_HEALTH_FAILED
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 1
        self.eh.on_health_check_result(msg)
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 2

        # when threshold exceeded request termination
        self.eh.on_health_check_result(msg)
        assert self.vmm.start_vm_termination.called

    def test_health_check_result_on_fail_from_in_use(self):
        # on fail set state to check failed state and increment fails counter
        self.vmd = VmDescriptor(self.vm_ip, self.vm_name, self.group, VmStates.IN_USE)
        self.vmd.store(self.rc)

        self.vmm.get_vm_by_name.return_value = self.vmd
        msg = self.msg
        msg["result"] = "failed"

        assert self.vmd.get_field(self.rc, "state") == VmStates.IN_USE
        self.eh.on_health_check_result(msg)
        assert self.vmd.get_field(self.rc, "state") == VmStates.IN_USE
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 1
        self.eh.on_health_check_result(msg)
        assert self.vmd.get_field(self.rc, "state") == VmStates.IN_USE
        assert int(self.vmd.get_field(self.rc, "check_fails")) == 2

        # when threshold exceeded request termination do NOT terminate it
        self.eh.on_health_check_result(msg)
        assert self.vmd.get_field(self.rc, "state") == VmStates.IN_USE
        assert not self.vmm.start_vm_termination.called

    def test_health_check_result_on_wrong_states(self):
        self.vmd = VmDescriptor(self.vm_ip, self.vm_name, self.group, VmStates.GOT_IP)
        self.vmd.store(self.rc)
        self.vmm.get_vm_by_name.return_value = self.vmd

        self.vmd.store_field(self.rc, "check_fails", 100)
        msg = self.msg
        msg["result"] = "failed"
        for state in [VmStates.TERMINATING, VmStates.GOT_IP, VmStates.READY]:
            self.vmd.store_field(self.rc, "state", state)
            self.eh.on_health_check_result(msg)

            assert int(self.vmd.get_field(self.rc, "check_fails")) == 100
            assert self.vmd.get_field(self.rc, "state") == state
            assert not self.vmm.terminate_vm.called

    def test_on_vm_termination_result_ok(self):
        msg = self.msg
        msg["result"] = "OK"
        self.eh.on_vm_termination_result(msg)
        assert self.vmm.remove_vm_from_pool.called
        msg.pop("vm_name")
        self.vmm.remove_vm_from_pool.reset_mock()
        self.eh.on_vm_termination_result(msg)
        assert not self.vmm.remove_vm_from_pool.called

    def test_on_vm_termination_result_fail(self):
        msg = self.msg
        msg["result"] = "failed"
        self.eh.on_vm_termination_result(msg)
        assert not self.vmm.remove_vm_from_pool.called

    def test_dummy_run(self, mc_setproctitle, mc_recycle):
        #  dummy test, mainly for perfect coverage
        self.eh.start_listen = types.MethodType(MagicMock(), self.eh)
        self.eh.run()

        assert mc_recycle.called
        assert self.eh.start_listen.called

    def test_dummy_terminate(self, mc_setproctitle, mc_recycle):
        #  dummy test, mainly for perfect coverage
        assert not self.eh.kill_received
        self.eh.do_recycle_proc = MagicMock()

        self.eh.terminate()

        assert self.eh.kill_received
        assert self.eh.do_recycle_proc.terminate.called
        assert self.eh.do_recycle_proc.join.called

    def test_start_test_listen(self):
        self.vmm.rc = MagicMock()
        mc_channel = MagicMock()
        self.vmm.rc.pubsub.return_value = mc_channel

        self.eh.handlers_map = MagicMock()

        def on_listen():
            if self.stage == 1:
                return None
            elif self.stage == 2:
                assert not self.eh.handlers_map.__getitem__.called
                return {}
            elif self.stage == 3:
                assert not self.eh.handlers_map.__getitem__.called
                return {"type": "subscribe"}
            elif self.stage == 4:
                assert not self.eh.handlers_map.__getitem__.called
                return {"type": "message"}
            elif self.stage == 5:
                assert not self.eh.handlers_map.__getitem__.called
                return {"type": "message", "data": "{{"}
            elif self.stage == 6:
                assert not self.eh.handlers_map.__getitem__.called
                return {"type": "message", "data": json.dumps({})}  # no topic
            elif self.stage == 7:
                assert not self.eh.handlers_map.__getitem__.called
                self.eh.handlers_map.__contains__.return_value = False               #
                self.eh.handlers_map.__getitem__.side_effect = KeyError()            #
                return {"type": "message", "data": json.dumps({"topic": "foobar"})}  # no handler for topic
            elif self.stage == 8:
                # import ipdb; ipdb.set_trace()
                assert not self.eh.handlers_map.__getitem__.called
                assert self.eh.handlers_map.__contains__.called

                self.eh.handlers_map.__contains__.return_value = True
                self.eh.handlers_map.__contains__.reset_mock()
                self.eh.handlers_map.__getitem__.reset_mock()
                self.eh.handlers_map.__getitem__.return_value.side_effect = IOError()  #
                return {"type": "message", "data": json.dumps({"topic": "foobar"})}    # handler produces exception
            elif self.stage == 9:
                assert self.eh.handlers_map.__getitem__.called
                assert self.eh.handlers_map.__contains__.called

                self.eh.handlers_map.__contains__.return_value = True
                self.eh.handlers_map.__getitem__.reset_mock()
                self.eh.handlers_map.__getitem__.return_value = None
                return {"type": "message", "data": json.dumps({"topic": "foobar"})}    # handler invoked ok

            else:
                self.eh.kill_received = True

        def my_gen():
            self.stage += 1
            while True:
                yield on_listen()
                self.stage += 1

        mc_channel.listen.return_value = my_gen()

        self.eh.start_listen()
        assert mc_channel.listen.called
