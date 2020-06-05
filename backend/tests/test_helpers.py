# coding: utf-8

from munch import Munch
import json
import logging

from copr_backend.background_worker_build import BackendError
from copr_backend.helpers import get_redis_logger, get_chroot_arch, \
        format_filename, get_redis_connection
from copr_backend.constants import LOG_REDIS_FIFO

"""
SOME TESTS REQUIRES RUNNING REDIS
"""

MODULE_REF = "copr_backend.helpers"


class TestHelpers(object):

    def setup_method(self, method):
        self.opts = Munch(
            redis_db=9,
            redis_port=7777,
        )

        self.rc = get_redis_connection(self.opts)
        # remove leftovers from previous tests
        self.rc.delete(LOG_REDIS_FIFO)

    def teardown_method(self, method):
        pass

    def test_redis_logger_exception(self):
        log = get_redis_logger(self.opts, "copr_backend.test", "test")
        try:
            raise BackendError("foobar")
        except Exception as err:
            log.exception("error occurred: {}".format(err))

        (_, raw_message) = self.rc.blpop([LOG_REDIS_FIFO])
        data = json.loads(raw_message)
        assert data.get("who") == "test"
        assert data.get("levelno") == logging.ERROR
        assert "error occurred: Backend process error: foobar\n" in data["msg"]
        assert 'raise BackendError("foobar")' in data["msg"]

    def test_get_chroot_arch(self):
        assert get_chroot_arch("fedora-26-x86_64") == "x86_64"
        assert get_chroot_arch("epel-7-ppc64le") == "ppc64le"
        assert get_chroot_arch("epel-7-ppc64") == "ppc64"

    def test_format_filename(self):
        assert format_filename("ed", "1.14.2", "5.fc30", "", "x86_64") == "ed-1.14.2-5.fc30.x86_64"
        assert format_filename("ed", "1.14.2", "5.fc30", "", "x86_64", zero_epoch=True) == "ed-0:1.14.2-5.fc30.x86_64"
        assert format_filename("ed", "1.14.2", "5.fc30", "2", "x86_64") == "ed-2:1.14.2-5.fc30.x86_64"

        split = ("ed", "1.14.2", "5.fc30", "2", "x86_64")
        assert format_filename(zero_epoch=True, *split) == "ed-2:1.14.2-5.fc30.x86_64"
