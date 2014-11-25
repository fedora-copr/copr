import os

from collections import defaultdict
import json
from pprint import pprint
from _pytest.capture import capsys
import pytest
import copy
import tempfile
import shutil

import six
import time

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


from backend.dispatcher import Worker


class TestWorkerStatic(object):

    def setup_method(self, method):
        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

        self.pkg_pdn = "foobar"
        self.pkg_name = "{}.src.rpm".format(self.pkg_pdn)
        self.pkg_path = os.path.join(self.tmp_dir_path, self.pkg_name)
        with open(self.pkg_path, "w") as handle:
            handle.write("1")

        self.chroot = "fedora-20-x86_64"

    def teardown_method(self, method):
        # print("\nremove: {}".format(self.tmp_dir_path))
        shutil.rmtree(self.tmp_dir_path)

    def test_pkg_built_before(self):
        assert not Worker.pkg_built_before(self.pkg_path, self.chroot, self.tmp_dir_path)
        target_dir = os.path.join(self.tmp_dir_path, self.chroot, self.pkg_pdn)
        os.makedirs(target_dir)
        assert not Worker.pkg_built_before(self.pkg_path, self.chroot, self.tmp_dir_path)
        with open(os.path.join(target_dir, "fail"), "w") as handle:
            handle.write("undone")
        assert not Worker.pkg_built_before(self.pkg_path, self.chroot, self.tmp_dir_path)
        os.remove(os.path.join(target_dir, "fail"))
        with open(os.path.join(target_dir, "success"), "w") as handle:
            handle.write("done")
        assert Worker.pkg_built_before(self.pkg_path, self.chroot, self.tmp_dir_path)
