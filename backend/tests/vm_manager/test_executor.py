# coding: utf-8

from multiprocessing import Queue
import types

from bunch import Bunch
import six
import time

from backend.helpers import get_redis_connection
from backend.vm_manage.executor import Executor


if six.PY3:
    from unittest import mock
else:
    import mock

import pytest


"""
REQUIRES RUNNING REDIS
TODO: look if https://github.com/locationlabs/mockredis can be used
"""

MODULE_REF = "backend.vm_manage.executor"

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


class TestExecutor(object):

    def setup_method(self, method):
        self.opts = Bunch(
            redis_db=9,
            ssh=Bunch(
                transport="ssh"
            ),
            build_groups={
                0: {
                    "spawn_playbook": "/spawn.yml",
                    "name": "base",
                    "archs": ["i386", "x86_64"]
                }
            }
        )

        self.queue = Queue()

        self.executor = Executor(self.opts, self.queue)

        self.rc = get_redis_connection(self.opts)

    def teardown_method(self, method):
        keys = self.rc.keys("*")
        if keys:
            self.rc.delete(*keys)

    def test_log(self, mc_time):
        mc_time.time.return_value = 1
        self.executor.log("foobar")
        mc_time.time.return_value = 2
        self.executor.log("barfoo", "bob")

        msg = self.queue.get()
        assert msg["what"] == "foobar"
        assert msg["when"] == 1
        assert msg["who"] == Executor.__name_for_log__

        msg = self.queue.get()
        assert msg["what"] == "barfoo"
        assert msg["when"] == 2
        assert msg["who"] == "bob"

    def test_recycle(self, mc_time):
        self.executor.last_recycle = 0
        mc_time.time.return_value = int(1.1 * self.executor.recycle_period)
        p1 = mock.MagicMock()
        p2 = mock.MagicMock()
        self.executor.child_processes.extend([p1, p2])
        p1.is_alive.return_value = True
        p2.is_alive.return_value = False

        self.executor.recycle()

        assert len(self.executor.child_processes) == 1
        assert self.executor.child_processes[0] == p1
        assert p2.join.called

        self.executor.last_recycle = self.executor.recycle_period
        p1.reset_mock()
        assert not p1.is_alive.called
        self.executor.recycle()
        assert not p1.is_alive.called
        self.executor.recycle(force=True)
        assert p1.is_alive.called

    def test_terminate(self):
        p1 = mock.MagicMock()
        p2 = mock.MagicMock()
        self.executor.child_processes.extend([p1, p2])

        self.executor.terminate()
        assert p1.terminate.called
        assert p2.terminate.called
        assert p1.join.called
        assert p2.join.called

    def test_children_number(self):
        mm = mock.MagicMock()
        self.executor.recycle = types.MethodType(mm, self.executor)
        assert self.executor.children_number == 0
        assert self.executor.recycle.called

        p1 = mock.MagicMock()
        p2 = mock.MagicMock()

        self.executor.child_processes.extend([p1, p2])
        assert self.executor.children_number == 2
