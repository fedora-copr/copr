# coding: utf-8

import datetime
import time
import pytest

from unittest import mock
from unittest.mock import MagicMock

from copr_dist_git import process_pool

MODULE_REF = 'copr_dist_git.process_pool'


class TestWorker(object):
    def test_timeout(self):
        w1 = process_pool.Worker(timeout=5)
        assert not w1.timeouted

        w1.timestamp -= datetime.timedelta(seconds=1)
        assert not w1.timeouted

        w1.timestamp -= datetime.timedelta(seconds=4)
        assert w1.timeouted

        w2 = process_pool.Worker(timeout=-1)
        assert w2.timeouted


class TestPool(object):
    def test_busy(self):
        pool = process_pool.Pool(workers=3)
        assert not pool.busy

        pool.extend([None, None])
        assert not pool.busy

        pool.append(None)
        assert pool.busy

    def test_remove_dead(self):
        w = process_pool.Worker(target=time.sleep, args=[1000])
        w.start()

        pool = process_pool.Pool(workers=3)
        pool.append(w)
        pool.remove_dead()
        assert list(pool) == [w]

        w.terminate()
        w.join()
        pool.remove_dead()
        assert list(pool) == []

    def test_terminate_timeouted(self):
        w = process_pool.Worker(target=time.sleep, args=[1000], timeout=-1, id="foo")
        w.start()

        pool = process_pool.Pool()
        pool.append(w)

        send_to_fe = MagicMock().method
        pool.terminate_timeouted(callback=send_to_fe)
        w.join()

        send_to_fe.assert_called_with({"build_id": "foo", "error": "import_timeout_exceeded"})
        assert not pool[0].is_alive()
