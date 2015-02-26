# coding: utf-8
from Queue import Empty
import json
import shutil
from subprocess import CalledProcessError
import tempfile
import time
from multiprocessing import Queue
import types

from bunch import Bunch
from redis import ConnectionError
import six
from backend.exceptions import CoprSpawnFailError

from backend.helpers import get_redis_connection
from backend.vm_manage import EventTopics, PUBSUB_MB
from backend.vm_manage.check import HealthChecker, check_health

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

MODULE_REF = "backend.vm_manage.check"

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
    with mock.patch("{}.run_ansible_playbook_once".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_ans_runner():
    with mock.patch("{}.Runner".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_grc():
    with mock.patch("{}.get_redis_connection".format(MODULE_REF)) as handle:
        yield handle


class TestChecker(object):

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.terminate_pb_path = "{}/terminate.yml".format(self.test_root_path)
        self.opts = Bunch(
            redis_db=9,
            ssh=Bunch(
                transport="ssh"
            ),
            build_groups={
                0: {
                    "terminate_playbook": self.terminate_pb_path,
                    "name": "base",
                    "archs": ["i386", "x86_64"],
                    # "terminate_vars": ["vm_name", "ip"],
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
        # self.try_spawn_args = '-c ssh {}'.format(self.spawn_pb_path)

        # self.callback = TestCallback()
        self.checker = MagicMock()
        self.terminator = MagicMock()

        self.queue = Queue()

        self.checker = HealthChecker(self.opts, self.queue)
        self.checker.recycle = types.MethodType(mock.MagicMock, self.terminator)
        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"
        self.group = 0
        self.username = "bob"

        self.rc = get_redis_connection(self.opts)
        self.log_msg_list = []

    def log_fn(self, msg):
        self.log_msg_list.append(msg)

    def teardown_method(self, method):
        shutil.rmtree(self.test_root_path)
        keys = self.rc.keys("*")
        if keys:
            self.rc.delete(*keys)

        self.log_msg_list = []

    def _get_all_from_queue(self):
        res = []
        while True:
            try:
                time.sleep(0.02)
                value = self.queue.get_nowait()
                res.append(value)
            except Empty:
                break
        return res

    def test_start_check(self, mc_process):
        p1 = mock.MagicMock()
        mc_process.return_value = p1

        self.checker.run_check_health(self.vm_name, self.vm_ip)
        assert mc_process.called
        assert self.checker.child_processes == [p1]
        assert p1.start.called

    def test_check_health_runner_no_response(self, mc_ans_runner, mc_grc):
        mc_runner = MagicMock()
        mc_ans_runner.return_value = mc_runner
        # mc_runner.connection.side_effect = IOError()

        mc_rc = MagicMock()
        mc_grc.return_value = mc_rc

        # didn't raise exception
        check_health(self.opts, self.queue, self.vm_name, self.vm_ip)
        assert mc_rc.publish.call_args[0][0] == PUBSUB_MB
        dict_result = json.loads(mc_rc.publish.call_args[0][1])
        assert dict_result["result"] == "failed"
        assert "VM is not responding to the testing playbook." in dict_result["msg"]

    def test_check_health_runner_exception(self, mc_ans_runner, mc_grc):
        mc_conn = MagicMock()
        mc_ans_runner.return_value = mc_conn
        mc_conn.run.side_effect = IOError()

        mc_rc = MagicMock()
        mc_grc.return_value = mc_rc

        # didn't raise exception
        check_health(self.opts, self.queue, self.vm_name, self.vm_ip)
        assert mc_rc.publish.call_args[0][0] == PUBSUB_MB
        dict_result = json.loads(mc_rc.publish.call_args[0][1])
        assert dict_result["result"] == "failed"
        assert "Failed to check  VM" in dict_result["msg"]
        assert "due to ansible error:" in dict_result["msg"]

    def test_check_health_runner_ok(self, mc_ans_runner, mc_grc):
        mc_conn = MagicMock()
        mc_ans_runner.return_value = mc_conn
        mc_conn.run.return_value = {"contacted": [self.vm_ip]}

        mc_rc = MagicMock()
        mc_grc.return_value = mc_rc

        # didn't raise exception
        check_health(self.opts, self.queue, self.vm_name, self.vm_ip)
        assert mc_rc.publish.call_args[0][0] == PUBSUB_MB
        dict_result = json.loads(mc_rc.publish.call_args[0][1])
        assert dict_result["result"] == "OK"

    def test_check_health_pubsub_publish_error(self, mc_ans_runner, mc_grc):
        mc_conn = MagicMock()
        mc_ans_runner.return_value = mc_conn
        mc_conn.run.return_value = {"contacted": [self.vm_ip]}

        mc_grc.side_effect = ConnectionError()

        # didn't raise exception
        check_health(self.opts, self.queue, self.vm_name, self.vm_ip)

        assert mc_conn.run.called
        msg_list = self._get_all_from_queue()

        # assert any("VM terminated" in ev["what"] for ev in msg_list)
        assert any("Failed to publish" in ev["what"] for ev in msg_list)
        assert mc_grc.called

