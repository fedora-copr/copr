# coding: utf-8

from munch import Munch

from backend.exceptions import BuilderError
from backend.helpers import get_redis_logger, get_chroot_arch, format_filename

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
