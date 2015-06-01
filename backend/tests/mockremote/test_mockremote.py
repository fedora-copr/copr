# coding: utf-8
import copy

from collections import defaultdict
from bunch import Bunch
from backend.exceptions import MockRemoteError, CoprSignError, BuilderError

import tempfile
import shutil
import os

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import patch, MagicMock
else:
    import mock
    from mock import patch, MagicMock

import pytest

from backend.mockremote import MockRemote, get_target_dir
from backend.job import BuildJob


MODULE_REF = "backend.mockremote"

def test_get_target_dir():
    for ch_dir, pkg_name, expected in [
        ("/tmp/", "copr-backend-1.46-1.git.35.8ba18d1.fc20.src.rpm",
            "/tmp/copr-backend-1.46-1.git.35.8ba18d1.fc20"),
        ("/tmp/foo/../bar", "copr-backend-1.46-1.git.35.8ba18d1.fc20.src.rpm",
            "/tmp/bar/copr-backend-1.46-1.git.35.8ba18d1.fc20"),
    ]:
        assert get_target_dir(ch_dir, pkg_name) == expected

STDOUT = "stdout"
STDERR = "stderr"
COPR_OWNER = "copr_owner"
COPR_NAME = "copr_name"
COPR_VENDOR = "vendor"


class TestMockRemote(object):

    @pytest.yield_fixture
    def f_mock_remote(self):
        patcher = mock.patch("backend.mockremote.Builder")
        self.mc_builder = patcher.start()
        self.mc_logger = MagicMock()
        self.mr = MockRemote(self.HOST, self.JOB, opts=self.OPTS, logger=self.mc_logger)
        self.mr.check()
        yield
        patcher.stop()

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.CHROOT = "fedora-20_i386"
        self.DESTDIR = os.path.join(self.test_root_path, COPR_OWNER, COPR_NAME)
        self.DESTDIR_CHROOT = os.path.join(self.DESTDIR, self.CHROOT)
        self.FRONT_URL = "htt://front.example.com"
        self.BASE_URL = "http://example.com/results"

        self.PKG_NAME = "foobar"
        self.PKG_VERSION = "1.2.3"

        self.HOST = "127.0.0.1"
        self.SRC_PKG_URL = "http://example.com/{}-{}.src.rpm".format(self.PKG_NAME, self.PKG_VERSION)
        self.JOB = BuildJob({
            "project_owner": COPR_OWNER,
            "project_name": COPR_NAME,
            "pkgs": self.SRC_PKG_URL,
            "repos": "",
            "build_id": 12345,
            "chroot": self.CHROOT,
        }, Bunch({
            "timeout": 1800,
            "destdir": self.test_root_path,
            "results_baseurl": "/tmp/",
        }))

        self.OPTS = Bunch({
            "do_sign": False,
            "results_baseurl": self.BASE_URL,
            "frontend_base_url": self.FRONT_URL,
        })

    def teardown_method(self, method):
        shutil.rmtree(self.test_root_path)

    def test_dummy(self, f_mock_remote):
        pass

    def test_no_job_chroot(self, f_mock_remote, capsys):
        job_2 = copy.deepcopy(self.JOB)
        job_2.chroot = None
        mr_2 = MockRemote(self.HOST, job_2, opts=self.OPTS, logger=self.mc_logger)
        with pytest.raises(MockRemoteError):
            mr_2.check()

        out, err = capsys.readouterr()

    @mock.patch("backend.mockremote.get_pubkey")
    def test_add_pubkey(self, mc_get_pubkey, f_mock_remote):
        self.mr.add_pubkey()
        assert mc_get_pubkey.called
        expected_path = os.path.join(self.DESTDIR, "pubkey.gpg")
        assert mc_get_pubkey.call_args == mock.call(
            COPR_OWNER, COPR_NAME, expected_path)

    @mock.patch("backend.mockremote.get_pubkey")
    def test_add_pubkey_on_exception(self, mc_get_pubkey, f_mock_remote):
        mc_get_pubkey.side_effect = CoprSignError("foobar")
        # doesn't raise an error
        self.mr.add_pubkey()

    @mock.patch("backend.mockremote.sign_rpms_in_dir")
    def test_sign_built_packages(self, mc_sign_rpms_in_dir, f_mock_remote):
        self.mr.sign_built_packages()
        assert mc_sign_rpms_in_dir.called

    @mock.patch("backend.mockremote.sign_rpms_in_dir")
    def test_sign_built_packages_exception(self, mc_sign_rpms_in_dir, f_mock_remote):
        mc_sign_rpms_in_dir.side_effect = IOError()
        # doesn't raise an error
        self.mr.sign_built_packages()

    @mock.patch("backend.mockremote.sign_rpms_in_dir")
    def test_sign_built_packages_exception_reraise(self, mc_sign_rpms_in_dir, f_mock_remote):
        mc_sign_rpms_in_dir.side_effect = MockRemoteError("foobar")
        with pytest.raises(MockRemoteError):
            self.mr.sign_built_packages()

    @mock.patch("backend.mockremote.createrepo")
    def test_do_createrepo(self, mc_createrepo, f_mock_remote):
        mc_createrepo.return_value = ("", "", "")
        self.mr.do_createrepo()
        assert mc_createrepo.called
        expected_call = mock.call(
            path=os.path.join(self.DESTDIR, self.CHROOT),
            front_url=self.FRONT_URL,
            base_url=u"/".join([self.BASE_URL, COPR_OWNER, COPR_NAME, self.CHROOT]),
            username=COPR_OWNER,
            projectname=COPR_NAME,
            lock=None,
        )
        assert mc_createrepo.call_args == expected_call

    @mock.patch("backend.mockremote.createrepo")
    def test_do_createrepo_on_error(self, mc_createrepo, f_mock_remote):
        err_msg = "error occured"
        mc_createrepo.return_value = ("", "", err_msg)
        # doesn't raise an error
        self.mr.do_createrepo()

    def test_on_success_build(self, f_mock_remote):
        self.mr.sign_built_packages = MagicMock()
        self.mr.do_createrepo = MagicMock()

        self.mr.opts.do_sign = False
        self.mr.on_success_build()

        assert not self.mr.sign_built_packages.called
        assert self.mr.do_createrepo.called

        self.mr.do_createrepo.reset()

        self.mr.opts.do_sign = True
        self.mr.on_success_build()

        assert self.mr.sign_built_packages.called
        assert self.mr.do_createrepo.called

    def test_prepare_build_dir_erase_fail_file(self, f_mock_remote):
        target_dir = os.path.join(
            self.DESTDIR, self.CHROOT,
            "{}-{}".format(self.PKG_NAME, self.PKG_VERSION))
        os.makedirs(target_dir)
        fail_path = os.path.join(target_dir, "fail")
        with open(fail_path, "w") as handle:
            handle.write("1")
        assert os.path.exists(fail_path)

        self.mr.prepare_build_dir()

        assert not os.path.exists(fail_path)

    def test_prepare_build_dir_erase_success_file(self, f_mock_remote):
        target_dir = os.path.join(
            self.DESTDIR, self.CHROOT,
            "{}-{}".format(self.PKG_NAME, self.PKG_VERSION))
        os.makedirs(target_dir)
        fail_path = os.path.join(target_dir, "success")
        with open(fail_path, "w") as handle:
            handle.write("1")
        assert os.path.exists(fail_path)

        self.mr.prepare_build_dir()

        assert not os.path.exists(fail_path)

    def test_prepare_build_dir_creates_dirs(self, f_mock_remote):
        self.mr.prepare_build_dir()
        target_dir = os.path.join(
            self.DESTDIR, self.CHROOT,
            "{}-{}".format(self.PKG_NAME, self.PKG_VERSION))
        assert os.path.exists(target_dir)

    def test_build_pkg_and_process_results(self, f_mock_remote):
        self.mr.on_success_build = MagicMock()
        self.mr.mark_dir_with_build_id = MagicMock()

        build_details = MagicMock()
        self.mr.builder.build.return_value = (build_details, STDOUT)

        result = self.mr.build_pkg_and_process_results()

        assert id(result) == id(build_details)

        assert self.mr.builder.build.called
        assert self.mr.builder.build.call_args == mock.call(self.SRC_PKG_URL)

        assert self.mr.builder.download.called
        assert self.mr.builder.download.call_args == \
            mock.call(self.SRC_PKG_URL, self.DESTDIR_CHROOT)

        assert self.mr.mark_dir_with_build_id.called
        assert self.mr.on_success_build.called

    def test_build_pkg_and_process_results_error_on_download(self, f_mock_remote):
        self.mr.builder.build.return_value = ({}, STDOUT)
        self.mr.builder.download.side_effect = BuilderError(msg="STDERR")

        self.mr.mark_dir_with_build_id = MagicMock()
        self.mr.on_success_build = MagicMock()
        with pytest.raises(MockRemoteError):
            self.mr.build_pkg_and_process_results()

        assert not self.mr.on_success_build.called
        assert self.mr.mark_dir_with_build_id.called

    def test_build_pkg_and_process_results_error_on_build(self, f_mock_remote):
        # self.mr.builder.build.return_value = ({}, STDOUT)
        self.mr.builder.build.side_effect = BuilderError(msg="STDERR")
        # self.mr.builder.download.return_value = BuilderError(msg="STDERR")

        self.mr.mark_dir_with_build_id = MagicMock()
        self.mr.on_success_build = MagicMock()
        with pytest.raises(MockRemoteError):
            self.mr.build_pkg_and_process_results()

        assert not self.mr.on_success_build.called
        assert self.mr.mark_dir_with_build_id.called

    def test_mark_dir_with_build_id(self, f_mock_remote):
        # TODO: create real test
        os.makedirs(os.path.join(self.DESTDIR_CHROOT,
                                 "{}-{}".format(self.PKG_NAME, self.PKG_VERSION)))

        info_file_path = os.path.join(self.DESTDIR_CHROOT,
                                      "{}-{}".format(self.PKG_NAME, self.PKG_VERSION),
                                      "build.info")
        assert not os.path.exists(info_file_path)
        self.mr.mark_dir_with_build_id()

        assert os.path.exists(info_file_path)
        with open(info_file_path) as handle:
            assert str(self.JOB.build_id) in handle.read()

        with mock.patch("__builtin__.open".format(MODULE_REF)) as mc_open:
            mc_open.side_effect = IOError()
            # do not raise an error
            self.mr.mark_dir_with_build_id()

    # def test_add_log_symlinks(self, f_mock_remote):
    #     base = os.path.join(self.DESTDIR_CHROOT,
    #                         "{}-{}".format(self.PKG_NAME, self.PKG_VERSION))
    #     os.makedirs(base)
    #
    #     names = ["build.log", "root.log"]
    #     for name in names:
    #         open(os.path.join(base, name + ".gz"), "a").close()
    #         assert not os.path.exists(os.path.join(base, name))
    #
    #     dir_name = "i_am_a_dir.log"
    #     os.mkdir(os.path.join(base, dir_name + ".gz"))
    #     assert not os.path.exists(os.path.join(base, dir_name))
    #
    #     self.mr.add_log_symlinks()
    #     assert not os.path.exists(os.path.join(base, dir_name))
    #     for name in names:
    #         assert os.path.exists(os.path.join(base, name))




