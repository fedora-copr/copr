# coding: utf-8
import json
import logging

import os
import copy
import tarfile
import tempfile
import shutil
import time
from bunch import Bunch
from pyrpkg import rpkgError
import pytest

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

from dist_git.dist_git_importer import DistGitImporter, SourceType, ImportTask
from dist_git.exceptions import PackageImportException, PackageDownloadException, PackageQueryException

MODULE_REF = 'dist_git.dist_git_importer'


@pytest.yield_fixture
def mc_dgcr():
    with mock.patch("{}.DistGitConfigReader".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_SourceProvider():
    with mock.patch("{}.SourceProvider".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_popen():
    with mock.patch("{}.Popen".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_call():
    with mock.patch("{}.call".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_get():
    with mock.patch("{}.get".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_post():
    with mock.patch("{}.post".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_urlretrieve():
    with mock.patch("{}.urlretrieve".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_pyrpkg_commands():
    with mock.patch("{}.Commands".format(MODULE_REF)) as handle:
        yield handle


if True:
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d] %(message)s',
        datefmt='%H:%M:%S'
    )


class TestDistGitImporter(object):
    def setup_method(self, method):
        self.tmp_dir_name = self.make_temp_dir()
        self.lookaside_location = os.path.join(self.tmp_dir_name, "lookaside")
        self.opts = Bunch({
            "frontend_base_url": "http://front",
            "frontend_auth": "secure_password",

            "lookaside_location": self.lookaside_location,

            "cgit_pkg_list_location": self.tmp_dir_name,
            "sleep_time": 10,
            "log_dir": self.tmp_dir_name
        })

        self.dgi = DistGitImporter(self.opts)

        self.USER_NAME = "foo"
        self.PROJECT_NAME = "bar"
        self.PACKAGE_NAME = "bar_app"
        self.PACKAGE_VERSION = "2:0.01-1.fc20"
        self.BRANCH = "f22"
        self.FILE_HASH = "1234abc"
        self.task_data_1 = {
            "task_id": 123,
            "user": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branch": self.BRANCH,
            "source_type": SourceType.SRPM_LINK,
            "source_json": json.dumps({"url": "http://example.com/pkg.src.rpm"})
        }
        self.task_data_2 = {
            "task_id": 124,
            "user": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branch": self.BRANCH,
            "source_type": SourceType.SRPM_UPLOAD,
            "source_json": json.dumps({"tmp": "tmp_2", "pkg": "pkg_2.src.rpm"})
        }

        self.task_1 = ImportTask.from_dict(self.task_data_1, self.opts)
        self.task_2 = ImportTask.from_dict(self.task_data_2, self.opts)

        self.fetched_srpm_path = "/tmp/none/"


    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_{}_{}".format(MODULE_REF, time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)
        os.mkdir(self.tmp_dir_name)
        return self.tmp_dir_name

    def test_try_to_obtain_new_task_empty(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": []}
        assert self.dgi.try_to_obtain_new_task() is None

    def test_try_to_obtain_handle_error(self, mc_get):
        for err in [IOError, OSError, ValueError]:
            mc_get.side_effect = err
            assert self.dgi.try_to_obtain_new_task() is None

    def test_try_to_obtain_ok(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.task_data_1, self.task_data_2]}
        task = self.dgi.try_to_obtain_new_task()
        assert task.task_id == self.task_data_1["task_id"]
        assert task.user == self.USER_NAME
        assert task.branch == self.BRANCH
        assert task.package_url == "http://example.com/pkg.src.rpm"

    def test_try_to_obtain_ok_2(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.task_data_2, self.task_data_1]}
        task = self.dgi.try_to_obtain_new_task()
        assert task.task_id == self.task_data_2["task_id"]
        assert task.user == self.USER_NAME
        assert task.branch == self.BRANCH
        assert task.package_url == "http://front/tmp/tmp_2/pkg_2.src.rpm"

    def test_try_to_obtain_new_task_unknown_source_type(self, mc_get):
        task_data = copy.deepcopy(self.task_data_1)
        task_data["source_type"] = 999999
        mc_get.return_value.json.return_value = {"builds": [task_data]}
        assert self.dgi.try_to_obtain_new_task() is None

    # def test_my_upload(self):
    #     filename = "source"
    #     source_path = os.path.join(self.tmp_dir_name, filename)
    #     with open(source_path, "w") as handle:
    #         handle.write("1")
    #
    #     reponame = self.PROJECT_NAME
    #     target = "/".join([
    #         self.lookaside_location, reponame, filename, self.FILE_HASH, filename
    #     ])
    #     assert not os.path.exists(target)
    #     self.dgi.my_upload(self.tmp_dir_name, reponame, filename, self.FILE_HASH)
    #     assert os.path.exists(target)

    # def test_git_import_srpm(self, mc_pyrpkg_commands):
    #     # stupid test, just for the coverage
    #     mc_cmd = MagicMock()
    #     mc_pyrpkg_commands.return_value = mc_cmd
    #     mc_cmd.commithash = self.FILE_HASH
    #
    #     filename = "source"
    #     source_path = os.path.join(self.tmp_dir_name, filename)
    #
    #     self.task_1.package_name = self.PACKAGE_NAME
    #     assert self.dgi.git_import_srpm(self.task_1, source_path) == self.FILE_HASH
    #
    #     # check exception handling
    #     for err in [IOError, OSError, ValueError]:
    #         mc_cmd.import_srpm.side_effect = err
    #         with pytest.raises(PackageImportException):
    #             self.dgi.git_import_srpm(self.task_1, source_path)
    #     mc_cmd.import_srpm.side_effect = None
    #
    #     mc_cmd.push.side_effect = rpkgError
    #     assert self.dgi.git_import_srpm(self.task_1, source_path) == self.FILE_HASH
    #
    #     for err in [IOError, OSError, ValueError]:
    #         mc_pyrpkg_commands.side_effect = err
    #         with pytest.raises(PackageImportException):
    #             self.dgi.git_import_srpm(self.task_1, source_path)

    def test_pkg_name_evr(self, mc_popen):
        mc_comm = MagicMock()
        mc_popen.return_value.returncode = 0
        mc_popen.return_value.communicate = mc_comm

        test_plan = [
            (("(none)", "0.1", "1.fc20"), "0.1-1.fc20"),
            (("2", "0.1", "1.fc20"), "2:0.1-1.fc20")
        ]
        for (e, v, r), expected in test_plan:
            mc_comm.return_value = ("foo {} {} {}".format(e, v, r), None)
            assert self.dgi.pkg_name_evr("/dev/null") == ("foo", expected)

    def test_pkg_name_evr_error_handling(self, mc_popen):
        mc_comm = MagicMock()
        mc_popen.return_value.communicate = mc_comm

        test_plan = [
            (("(none)", "0.1", "1.fc20"), "0.1-1.fc20"),
            (("2", "0.1", "1.fc20"), "2:0.1-1.fc20")
        ]

        mc_popen.side_effect = OSError
        with pytest.raises(PackageQueryException):
            self.dgi.pkg_name_evr("/dev/null")

        mc_popen.side_effect = None
        for (e, v, r), expected in test_plan:
            mc_comm.return_value = ("foo {} {} {}".format(e, v, r), "err msg")
            with pytest.raises(PackageQueryException):
                self.dgi.pkg_name_evr("/dev/null")

        for (e, v, r), expected in test_plan:
            mc_comm.return_value = ("", None)
            with pytest.raises(PackageQueryException):
                self.dgi.pkg_name_evr("/dev/null")

    def test_before_git_import(self, mc_call):
        # dummy test, just for coverage
        self.dgi.before_git_import(self.task_1)
        assert mc_call.called

    def test_after_git_import(self, mc_call):
        # dummy test, just for coverage
        self.dgi.after_git_import()
        assert mc_call.called

    def test_past_back(self, mc_post):
        dd = {"foo": "bar"}
        self.dgi.post_back(dd)
        assert mc_post.called

    def test_past_back_safe(self, mc_post):
        dd = {"foo": "bar"}
        self.dgi.post_back_safe(dd)
        assert mc_post.called
        mc_post.reset_mock()
        assert not mc_post.called

        mc_post.side_effect = IOError
        self.dgi.post_back_safe(dd)
        assert mc_post.called

    def test_do_import(self, mc_SourceProvider):
        internal_methods = [
            "pkg_name_evr",
            "before_git_import",
            "git_import_srpm",
            "after_git_import",
            "post_back"
        ]
        mc_methods = {name: MagicMock() for name in internal_methods}
        for name, mc in mc_methods.items():
            setattr(self.dgi, name, mc)

        mc_methods["pkg_name_evr"].return_value = self.PACKAGE_NAME, self.PACKAGE_VERSION
        mc_methods["git_import_srpm"].return_value = self.FILE_HASH

        self.dgi.do_import(self.task_1)
        assert self.task_1.package_name == self.PACKAGE_NAME
        assert self.task_1.package_version == self.PACKAGE_VERSION
        assert self.task_1.git_hash == self.FILE_HASH

        for name in internal_methods:
            mc = mc_methods[name]
            for err in (IOError, PackageImportException, PackageDownloadException, PackageQueryException):
                mc.side_effect = err
                self.dgi.do_import(self.task_1)

            mc.side_effect = None

    def test_run(self, mc_time):
        self.dgi.try_to_obtain_new_task = MagicMock()
        self.dgi.do_import = MagicMock()

        def stop_run(*args, **kwargs):
            self.dgi.is_running = False

        mc_time.sleep.side_effect = stop_run

        self.dgi.try_to_obtain_new_task.return_value = None
        self.dgi.run()
        assert not self.dgi.do_import.called

        self.dgi.try_to_obtain_new_task.return_value = self.task_1
        self.dgi.do_import.side_effect = stop_run
        self.dgi.run()
        assert self.dgi.do_import.call_args == mock.call(self.task_1)

    # def test_main(self, mc_dgi, mc_dgcr):
    #     # dummy test, just for coverage
    #     mc_dgcr.return_value.read.return_value = self.opts
    #     main()
    #
    #     assert mc_dgi.called
    #
    #     mc_dgcr.return_value.read.side_effect = IOError()
    #     with pytest.raises(SystemExit):
    #         main()

