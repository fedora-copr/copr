# coding: utf-8

import os
import json
import logging
import tempfile
from munch import Munch

from copr_common.tree import walk_limited
from copr_common.redis_helpers import get_redis_connection
from copr_backend.background_worker_build import BackendError
from copr_backend.helpers import get_redis_logger, get_chroot_arch, format_filename
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
        log = get_redis_logger(self.opts, "copr_backend.test", "backend")
        try:
            raise BackendError("foobar")
        except Exception as err:
            log.exception("error occurred: {}".format(err))

        (_, raw_message) = self.rc.blpop([LOG_REDIS_FIFO])
        data = json.loads(raw_message)
        assert data.get("who") == "backend"
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

    @staticmethod
    def test_walk_limited():
        paths = [
            "user1/foo/srpm-builds/111/foo-1.src.rpm",
            "user1/foo/srpm-builds/111/foo-1.log",
            "user1/foo/srpm-builds/222/foo-2.log",
            "user1/foo/fedora-rawhide-x86_64/222-foo/foo-2.something.rpm",
            "user1/foo/fedora-rawhide-x86_64/note.txt",
            "user2/bar/.disable-appstream",
        ]
        with tempfile.TemporaryDirectory(prefix="copr-test-walk") as results:
            for path in paths:
                path = os.path.join(results, path)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "a").close()

            # The unlimited walk should be equal to built-in walk function
            assert list(os.walk(results)) == list(walk_limited(results))

            # Our fake directory strucutre isn't ten levels deep
            assert not list(walk_limited(results, mindepth=10))

            # A corner case with zero maxdepth
            output = list(walk_limited(results, maxdepth=0))
            root, subdirs, files = output[0]
            assert root == results
            assert set(subdirs) == {"user2", "user1"}
            assert files == []

            # Combination of both mindepth and maxdepth
            output = sorted(list(walk_limited(results, mindepth=3, maxdepth=3)))
            root, subdirs, files = output[0]
            assert root == os.path.join(results, "user1/foo/fedora-rawhide-x86_64")
            assert subdirs == ["222-foo"]
            assert files == ["note.txt"]

            root, subdirs, files = output[1]
            assert root == os.path.join(results, "user1/foo/srpm-builds")
            assert set(subdirs) == {"222", "111"}
            assert files == []
