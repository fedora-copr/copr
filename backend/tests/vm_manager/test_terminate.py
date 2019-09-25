# coding: utf-8
import shutil
from subprocess import CalledProcessError
import tempfile
import time
from multiprocessing import Queue
import types

from munch import Munch
from redis import ConnectionError
from backend.exceptions import CoprSpawnFailError

from backend.helpers import get_redis_connection
from backend.vm_manage import EventTopics
from backend.vm_manage.terminate import Terminator, terminate_vm

from unittest import mock, skip
from unittest.mock import MagicMock
import pytest


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "backend.vm_manage.terminate"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_terminate_vm():
    with mock.patch("{}.terminate_vm".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_process():
    with mock.patch("{}.Process".format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_run_ans():
    with mock.patch("{}.run_ansible_playbook_cli".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_spawn_instance():
    with mock.patch("{}.spawn_instance".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_grc():
    with mock.patch("{}.get_redis_connection".format(MODULE_REF)) as handle:
        yield handle


class TestTerminate(object):

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.terminate_pb_path = "{}/terminate.yml".format(self.test_root_path)
        self.opts = Munch(
            redis_port=7777,
            ssh=Munch(
                transport="ssh"
            ),
            build_groups={
                0: {
                    "terminate_playbook": self.terminate_pb_path,
                    "name": "base",
                    "archs": ["i386", "x86_64"],
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            timeout=1800,
            # destdir=self.tmp_dir_path,
            results_baseurl="/tmp",
        )
        self.grl_patcher = mock.patch("{}.get_redis_logger".format(MODULE_REF))
        self.grl_patcher.start()
        # self.try_spawn_args = '-c ssh {}'.format(self.spawn_pb_path)

        # self.callback = TestCallback()
        self.checker = MagicMock()
        self.terminator = MagicMock()

        self.terminator = Terminator(self.opts)
        self.terminator.recycle = types.MethodType(mock.MagicMock, self.terminator)
        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"
        self.group = 0
        self.username = "bob"

        self.rc = get_redis_connection(self.opts)
        self.log_msg_list = []

        self.logger = MagicMock()

    def teardown_method(self, method):
        shutil.rmtree(self.test_root_path)
        keys = self.rc.keys("*")
        if keys:
            self.rc.delete(*keys)

        self.grl_patcher.stop()

    def touch_pb(self):
        with open(self.terminate_pb_path, "w") as handle:
            handle.write("foobar")

    # def test_start_terminate(self, mc_process):
    #     # mc_spawn_instance.return_value = {"vm_name": self.vm_name, "ip": self.vm_ip}
    #
    #     # undefined group
    #     with pytest.raises(CoprSpawnFailError):
    #         self.terminator.terminate_vm(group=1, vm_name=self.vm_name, vm_ip=self.vm_ip)
    #
    #     # missing playbook
    #     with pytest.raises(CoprSpawnFailError):
    #         self.terminator.terminate_vm(group=0, vm_name=self.vm_name, vm_ip=self.vm_ip)
    #
    #     # None playbook
    #     self.opts.build_groups[0]["terminate_playbook"] = None
    #     with pytest.raises(CoprSpawnFailError):
    #         self.terminator.terminate_vm(group=0, vm_name=self.vm_name, vm_ip=self.vm_ip)
    #
    #     self.opts.build_groups[0]["terminate_playbook"] = self.terminate_pb_path
    #     self.touch_pb()
    #
    #     p1 = mock.MagicMock()
    #     mc_process.return_value = p1
    #
    #     self.terminator.terminate_vm(group=0, vm_name=self.vm_name, vm_ip=self.vm_ip)
    #     assert mc_process.called
    #     assert self.terminator.child_processes == [p1]
    #     assert p1.start.called

    def test_terminate_vm_on_error(self, mc_run_ans):
        mc_run_ans.side_effect = CalledProcessError(0, cmd=["ls"])

        # doesn't raise an error
        terminate_vm(self.opts, self.terminate_pb_path, 0, self.vm_name, self.vm_ip)

    @skip("Fixme or remove, test doesn't work.")
    def test_do_spawn_and_publish_ok(self, mc_run_ans, mc_grc):
        mc_rc = mock.MagicMock()
        mc_grc.return_value = mc_rc

        terminate_vm(self.opts, self.terminate_pb_path, 0, self.vm_name, self.vm_ip)

        assert mc_run_ans.called
        expected_cmd = '-c ssh {} --extra-vars=\'{{"copr_task": {{"vm_name": "{}", "ip": "{}"}}}}\''.format(
            self.terminate_pb_path, self.vm_name, self.vm_ip)

        assert expected_cmd == mc_run_ans.call_args[:-1][0][0]

        assert mc_grc.called
        assert mc_rc.publish.called

        expected_call = mock.call(
            'copr:backend:vm:pubsub::',
            '{"vm_ip": "127.0.0.1", "vm_name": "localhost", '
            '"topic": "vm_terminated", "group": 0, "result": "OK"}')
        assert mc_rc.publish.call_args == expected_call

    @skip("Fixme or remove, test doesn't work.")
    def test_do_spawn_and_publish_error(self, mc_run_ans, mc_grc):
        mc_grc.side_effect = ConnectionError()

        terminate_vm(self.opts, self.terminate_pb_path, 0, self.vm_name, self.vm_ip)

        assert mc_run_ans.called
        expected_cmd = '-c ssh {} --extra-vars=\'{{"copr_task": {{"vm_name": "{}", "ip": "{}"}}}}\''.format(
            self.terminate_pb_path, self.vm_name, self.vm_ip)

        assert expected_cmd == mc_run_ans.call_args[:-1][0][0]
        assert mc_grc.called
