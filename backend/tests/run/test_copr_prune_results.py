# coding: utf-8
import logging
import os
import sys
import shutil
import tarfile
import tempfile
import time
from bunch import Bunch
from subprocess import Popen, PIPE

import pytest

import six
if six.PY3:
    from unittest import mock
else:
    import mock
    from mock import MagicMock



sys.path.append("../../run")


MODULE_REF = "copr_prune_results"

@pytest.yield_fixture
def mc_popen():
    with mock.patch("{}.Popen".format(MODULE_REF)) as handle:
        yield handle


from copr_prune_results import Pruner


def assert_same_dirs(a, b):
    proc = Popen(["diff", "-r", a, b], stdout=PIPE, stdin=PIPE)
    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        raise AssertionError("Directories {}, {} aren't equal, diff out: \n {} \n {}"
                             .format(a, b, stdout, stderr))

class TestPruneResults(object):

    def setup_method(self, method):
        self.tmp_dir_name = None
        self.test_time = time.time()
        self.make_temp_dir()

        self.pkg_1 = "copr-backend-1.59-1.git.1.7ed2b8d.fc20"
        self.pkg_1_obsolete = "copr-backend-1.40-1.fc20"
        self.pkg_2 = "hello-2.8-1.fc20"
        self.pkg_2_obsolete = "hello-1.0.fc20"
        self.prj = "foox"
        self.chroots = ["fedora-20-i386", "fedora-20-x86_64",
                        "fedora-21-i386", "fedora-21-x86_64"]
        self.opts = Bunch(
            days=14,

            find_obsolete_script=os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                             "run", "copr_find_obsolete_builds.sh"))


        )

        self.log_file_path = os.path.join(self.tmp_dir_name, "_unittest.log")
        logging.basicConfig(
            # filename=self.log_file_path,
            stream=sys.stdout,
            format='[%(asctime)s][%(levelname)6s]: %(message)s',
            level=logging.DEBUG
        )
        self.log = logging.getLogger(__name__)
        self.log.info("setup method done")

        self.username = "vgologuz"
        self.coprname = "foox"

    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_action_{}".format(self.test_time)
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)

        os.mkdir(self.tmp_dir_name)
        self.expect_dir_name = os.path.join(self.tmp_dir_name, "_expect")
        os.mkdir(self.expect_dir_name)

        self.unpack_resource("foox.tar.gz")
        self.unpack_resource("foox.tar.gz", self.expect_dir_name)

        return self.tmp_dir_name

    def unpack_resource(self, resource_name, target=None):
        if self.tmp_dir_name is None:
            self.make_temp_dir()

        src_path = os.path.join(os.path.dirname(__file__), "..",
                                "_resources", resource_name)

        with tarfile.open(src_path, "r:gz") as tar_file:
            tar_file.extractall(target or self.tmp_dir_name)


    @pytest.fixture
    def test_pruner(self):
        self.pruner = Pruner(self.opts)

        return self.pruner

    def test_prune_old_failed(self, test_pruner):
        """
        Delete if build with "fail" fail with mtime > 14 days

        """
        # TODO: what neither fail or success are present?

        shutil.move(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_1, "success"),
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_1, "fail"),)
        shutil.move(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_2, "success"),
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_2, "fail"),)
        shutil.move(
            os.path.join(self.expect_dir_name, self.prj, self.chroots[0], self.pkg_2, "success"),
            os.path.join(self.expect_dir_name, self.prj, self.chroots[0], self.pkg_2, "fail"),)

        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_1, "fail"), (0, 0))
        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_2, "fail"),
                 (time.time(), time.time()))

        shutil.rmtree(os.path.join(self.expect_dir_name, self.prj, self.chroots[0], self.pkg_1))

        self.pruner.prune_failed_builds(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]))

        assert_same_dirs(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]),
            os.path.join(self.expect_dir_name, self.prj, self.chroots[0]),
        )

    def test_prune_obsolete_builds(self, test_pruner):

        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_1, "success"), (0, 0))
        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_2, "success"), (0, 0))

        # old obsolete build folder should be removed
        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_2_obsolete, "success"), (0, 0))
        shutil.rmtree(os.path.join(self.expect_dir_name, self.prj, self.chroots[0], self.pkg_2_obsolete))

        # recent obsolete build should remain
        os.utime(os.path.join(self.tmp_dir_name, self.prj, self.chroots[0], self.pkg_1_obsolete, "success"),
                 (time.time(), time.time()))

        self.pruner.prune_obsolete_success_builds(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]),
            self.username, self.coprname
        )

        assert_same_dirs(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]),
            os.path.join(self.expect_dir_name, self.prj, self.chroots[0]),
        )

    def test_prune_obsolete_builds_handle_script_error(self, test_pruner, mc_popen):
        mc_handle = MagicMock()
        mc_popen.return_value = mc_handle
        mc_handle.returncode = 1
        mc_handle.communicate.return_value = ("foo", "bar")

        # doesn't touch FS if `find_obsolete_build` produce error return code
        self.pruner.prune_obsolete_success_builds(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]),
            self.username, self.coprname
        )
        assert mc_popen.called

        assert_same_dirs(
            os.path.join(self.tmp_dir_name, self.prj, self.chroots[0]),
            os.path.join(self.expect_dir_name, self.prj, self.chroots[0]),
        )
