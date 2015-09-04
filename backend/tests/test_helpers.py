# coding: utf-8


from Queue import Empty
import json
import shutil
from subprocess import CalledProcessError
import tempfile
import time
from multiprocessing import Queue
import types

from munch import Munch
from redis import ConnectionError
import six
from backend.exceptions import CoprSpawnFailError

from backend.exceptions import BuilderError
from backend.helpers import get_redis_connection, get_redis_logger, BackendConfigReader
from backend.vm_manage import EventTopics, PUBSUB_MB
from backend.vm_manage.check import HealthChecker, check_health

if six.PY3:
    from unittest import mock
else:
    import mock
    from mock import MagicMock

import pytest


"""
SOME TESTS REQUIRES RUNNING REDIS
"""

MODULE_REF = "backend.helpers"


class TestHelpers(object):

    def setup_method(self, method):
        self.opts = Munch(
            redis_db=9,
            redis_port=7777,
        )

    def teardown_method(self, method):
        pass

    def test_redis_logger_exception(self):
        log = get_redis_logger(self.opts, "backend.test", "test")
        try:
            raise BuilderError("foobar", return_code=1, stdout="STDOUT", stderr="STDERR")
        except Exception as err:
            log.exception("error occurred: {}".format(err))
