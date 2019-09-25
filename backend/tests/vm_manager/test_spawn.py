# coding: utf-8
import shutil
import tempfile
import time
from multiprocessing import Queue
import types

from munch import Munch
from redis import ConnectionError
from backend.exceptions import CoprSpawnFailError

from backend.helpers import get_redis_connection
from backend.vm_manage.spawn import Spawner, spawn_instance, do_spawn_and_publish

from unittest import mock, skip
from unittest.mock import MagicMock
import pytest


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "backend.vm_manage.spawn"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_spawn_instance():
    with mock.patch("{}.spawn_instance".format(MODULE_REF)) as handle:
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


class TestSpawner(object):

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.spawn_pb_path = "{}/spawn.yml".format(self.test_root_path)
        self.opts = Munch(
            redis_db=9,
            redis_port=7777,
            ssh=Munch(
                transport="ssh"
            ),
            build_groups={
                0: {
                    "spawn_playbook": self.spawn_pb_path,
                    "name": "base",
                    "archs": ["i386", "x86_64"]
                }
            },

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            timeout=1800,
            # destdir=self.tmp_dir_path,
            results_baseurl="/tmp",
        )
        self.try_spawn_args = '-c ssh {}'.format(self.spawn_pb_path)

        self.grl_patcher = mock.patch("{}.get_redis_logger".format(MODULE_REF))
        self.grl_patcher.start()

        self.checker = MagicMock()
        self.terminator = MagicMock()

        self.spawner = Spawner(self.opts)
        self.spawner.recycle = types.MethodType(mock.MagicMock, self.spawner)
        self.vm_ip = "127.0.0.1"
        self.vm_name = "localhost"
        self.group = 0
        self.username = "bob"

        self.rc = get_redis_connection(self.opts)

        self.logger = MagicMock()

    def teardown_method(self, method):
        self.grl_patcher.stop()
        shutil.rmtree(self.test_root_path)
        keys = self.rc.keys("*")
        if keys:
            self.rc.delete(*keys)

    def touch_pb(self):
        with open(self.spawn_pb_path, "w") as handle:
            handle.write("foobar")

    # def test_start_spawn(self, mc_spawn_instance, mc_process):
    #     mc_spawn_instance.return_value = {"vm_name": self.vm_name, "ip": self.vm_ip}
    #
    #     # undefined group
    #     with pytest.raises(CoprSpawnFailError):
    #         self.spawner.start_spawn(1)
    #
    #     # missing playbook
    #     with pytest.raises(CoprSpawnFailError):
    #         self.spawner.start_spawn(0)
    #
    #     # None playbook
    #     self.opts.build_groups[0]["spawn_playbook"] = None
    #     with pytest.raises(CoprSpawnFailError):
    #         self.spawner.start_spawn(0)
    #
    #     self.opts.build_groups[0]["spawn_playbook"] = self.spawn_pb_path
    #     self.touch_pb()
    #
    #     p1 = mock.MagicMock()
    #     mc_process.return_value = p1
    #
    #     self.spawner.start_spawn(0)
    #     assert mc_process.called
    #     assert self.spawner.child_processes == [p1]
    #     assert p1.start.called

    def test_spawn_no_result(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.return_value = None
        with pytest.raises(CoprSpawnFailError):
            spawn_instance(self.spawn_pb_path, self.logger)

    @skip("Fixme or remove, test doesn't work.")
    def test_spawn_ansible_call_error(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.side_effect = Exception("foobar")
        with pytest.raises(CoprSpawnFailError) as err:
            spawn_instance(self.spawn_pb_path, self.logger)

        assert "Error during ansible invocation" in err.value.msg

    def test_spawn_no_ip_in_result(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.return_value = "foobar"
        with pytest.raises(CoprSpawnFailError) as err:
            spawn_instance(self.spawn_pb_path, self.logger)

        assert "No ip in the result" in err.value.msg

    def test_spawn_bad_ip(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.return_value = "\"IP=foobar\"  \"vm_name=foobar\""
        with pytest.raises(CoprSpawnFailError) as err:
            spawn_instance(self.spawn_pb_path, self.logger)

        assert "Invalid IP" in err.value.msg

        for bad_ip in ["256.0.0.2", "not-an-ip", "example.com", ""]:
            mc_run_ans.return_value = "\"IP={}\" \"vm_name=foobar\"".format(bad_ip)
            with pytest.raises(CoprSpawnFailError) as err:
                spawn_instance(self.spawn_pb_path, self.logger)

    def test_spawn_no_vm_name(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.return_value = "\"IP=foobar\""
        with pytest.raises(CoprSpawnFailError) as err:
            spawn_instance(self.spawn_pb_path, self.logger)

        assert "No vm_name" in err.value.msg

    def test_spawn_ok(self, mc_run_ans):
        self.touch_pb()
        mc_run_ans.return_value = " \"IP=127.0.0.1\" \"vm_name=foobar\""

        result = spawn_instance(self.spawn_pb_path, self.logger)
        assert result == {'vm_ip': '127.0.0.1', 'vm_name': 'foobar'}

    @skip("Fixme or remove, test doesn't work.")
    def test_do_spawn_and_publish_copr_spawn_error(self, mc_spawn_instance, mc_grc):
        mc_spawn_instance.side_effect = CoprSpawnFailError("foobar")
        result = do_spawn_and_publish(self.opts, self.spawn_pb_path, self.group)
        assert result is None
        assert not mc_grc.called

    def test_do_spawn_and_publish_any_spawn_error(self, mc_spawn_instance, mc_grc):
        mc_spawn_instance.side_effect = OSError("foobar")
        result = do_spawn_and_publish(self.opts, self.spawn_pb_path, self.group)
        assert result is None
        assert not mc_grc.called

    @skip("Fixme or remove, test doesn't work.")
    def test_do_spawn_and_publish_ok(self, mc_spawn_instance, mc_grc):
        mc_rc = mock.MagicMock()
        mc_grc.return_value = mc_rc
        mc_spawn_instance.return_value = {"result": "foobar"}

        do_spawn_and_publish(self.opts, self.spawn_pb_path, self.group)
        assert mc_grc.called
        assert mc_rc.publish.called
        assert mc_rc.publish.call_args == mock.call(
            'copr:backend:vm:pubsub::',
            '{"topic": "vm_spawned", "group": 0, "result": "foobar"}')

    def test_do_spawn_and_publish_publish_error(self, mc_spawn_instance, mc_grc):
        mc_spawn_instance.return_value = {"result": "foobar"}
        mc_grc.side_effect = ConnectionError()

        do_spawn_and_publish(self.opts, self.spawn_pb_path, self.group)
        assert mc_grc.called
