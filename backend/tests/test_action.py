import os
import json
import tempfile
import shutil
import time
import tarfile
from munch import Munch

import pytest

import unittest
from unittest import mock
from unittest.mock import MagicMock

from backend.actions import Action, ActionType, ActionResult
from backend.exceptions import CreateRepoError, CoprKeygenRequestError
from requests import RequestException

import os

RESULTS_ROOT_URL = "http://example.com/results"
STDOUT = "stdout"
STDERR = "stderr"


@mock.patch("backend.actions.time")
class TestAction(object):

    def setup_method(self, method):
        self.tmp_dir_name = None

        self.test_time = time.time()

        self.pkgs = ["foo.src.rpm"]
        self.pkgs_stripped = ["foo"]

        self.ext_data_for_delete_build = json.dumps({
            "src_pkg_name": self.pkgs_stripped[0],
            "ownername": "foo",
            "projectname": "bar",
            "project_dirname": "bar",
            "chroot_builddirs": {
                "srpm-builds": ["00001", "00002"],
                "fedora-rawhide-x86_64": ["00001-foo", "00002-baz"],
            },
        })

        self.opts = Munch(
            redis_db=9,
            redis_port=7777,

            destdir="/var/lib/copr/public_html/results/",
            frontend_base_url=None,
            results_baseurl=RESULTS_ROOT_URL,

            do_sign=False,

            build_deleting_without_createrepo="",
            keygen_host="example.com"
        )

        self.lockpath = tempfile.mkdtemp(prefix="copr-test-lockpath")
        self.os_env_patcher = mock.patch.dict(os.environ, {
            'COPR_TESTSUITE_NO_OUTPUT': '1',
            'COPR_TESTSUITE_LOCKPATH': self.lockpath,
            'PATH': os.environ['PATH']+':run',
        })
        self.os_env_patcher.start()

    def teardown_method(self, method):
        self.rm_tmp_dir()
        shutil.rmtree(self.lockpath)
        self.os_env_patcher.stop()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_action_{}".format(time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)

        os.mkdir(self.tmp_dir_name)
        os.mkdir(os.path.join(self.tmp_dir_name, "old_dir"))

        self.test_content = "time: {}\n".format(self.test_time)

        return self.tmp_dir_name

    def unpack_resource(self, resource_name):
        if self.tmp_dir_name is None:
            self.make_temp_dir()

        src_path = os.path.join(os.path.dirname(__file__),
                                "_resources", resource_name)

        with tarfile.open(src_path, "r:gz") as tfile:
            tfile.extractall(os.path.join(self.tmp_dir_name, "old_dir"))

    def test_action_run_legal_flag(self, mc_time):
        mc_time.time.return_value = self.test_time
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.LEGAL_FLAG,
                "id": 1
            },
        )
        test_action.run()

        self.dummy = str(test_action)

    @mock.patch("backend.actions.copy_tree")
    @mock.patch("backend.actions.os.path.exists")
    @mock.patch("backend.actions.unsign_rpms_in_dir")
    @mock.patch("backend.actions.subprocess.call")
    def test_action_handle_forks(self, mc_call, mc_unsign_rpms_in_dir, mc_exists, mc_copy_tree, mc_time):
        mc_time.time.return_value = self.test_time
        mc_exists = True
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.FORK,
                "id": 1,
                "object_type": "copr",
                "data": json.dumps(
                    {
                       'builds_map':
                        {
                            'srpm-builds': {
                                '00000002': '00000009', '00000005': '00000010'},
                            'fedora-17-x86_64': {
                                '00000002-pkg1': '00000009-pkg1', '00000005-pkg2': '00000010-pkg2'},
                            'fedora-17-i386': {
                                '00000002-pkg1': '00000009-pkg1', '00000005-pkg2': '00000010-pkg2'}
                        },
                        "user": "thrnciar",
                        "copr": "source-copr"
                    }),
                "old_value": "thrnciar/source-copr",
                "new_value": "thrnciar/destination-copr",
            },
        )
        test_action.run()
        calls = mc_copy_tree.call_args_list
        assert len(calls) == 6
        assert calls[0][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/srpm-builds/00000002",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/srpm-builds/00000009")
        assert calls[1][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/srpm-builds/00000005",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/srpm-builds/00000010")
        assert calls[2][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/fedora-17-x86_64/00000002-pkg1",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/fedora-17-x86_64/00000009-pkg1")
        assert calls[3][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/fedora-17-x86_64/00000005-pkg2",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/fedora-17-x86_64/00000010-pkg2")
        assert calls[4][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/fedora-17-i386/00000002-pkg1",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/fedora-17-i386/00000009-pkg1")
        assert calls[5][0] == (
            "/var/lib/copr/public_html/results/thrnciar/source-copr/fedora-17-i386/00000005-pkg2",
            "/var/lib/copr/public_html/results/thrnciar/destination-copr/fedora-17-i386/00000010-pkg2")

        # TODO: calling createrepo for srpm-builds is useless
        assert len(mc_call.call_args_list) == 3

        dirs = set()
        for call in mc_call.call_args_list:
            args = call[0][0]
            assert args[0] == 'copr-repo'
            dirs.add(args[1])

        for chroot in ['srpm-builds', 'fedora-17-i386', 'fedora-17-x86_64']:
            dir = '/var/lib/copr/public_html/results/thrnciar/destination-copr/' + chroot
            assert dir in dirs

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_rename(self, mc_time):

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        with open(os.path.join(self.tmp_dir_name, "old_dir", "foobar.txt"), "w") as handle:
            handle.write(self.test_content)

        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert not os.path.exists(os.path.join(tmp_dir, "old_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir", "foobar.txt"))
        with open(os.path.join(tmp_dir, "new_dir", "foobar.txt")) as handle:
            assert handle.read() == self.test_content

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_rename_success_on_empty_src(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        self.opts.destdir = os.path.join(tmp_dir, "dir-not-exists")
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_rename_failure_on_destination_exists(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        with open(os.path.join(self.tmp_dir_name, "old_dir", "foobar.txt"), "w") as handle:
            handle.write(self.test_content)
        os.mkdir(os.path.join(tmp_dir, "new_dir"))

        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.FAILURE
        assert result_dict["message"] == "Destination directory already exist."
        assert result_dict["job_ended_on"] == self.test_time

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir"))
        assert not os.path.exists(os.path.join(tmp_dir, "new_dir", "foobar.txt"))

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_delete_copr(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        self.opts.destdir = os.path.join(tmp_dir, "dir-not-exists")

        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                "old_value": "old_dir",
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 6
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_delete_copr_remove_folders(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        self.opts.destdir=tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                "old_value": "old_dir",
            },
            frontend_client=mc_front_cb
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 6
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert not os.path.exists(os.path.join(tmp_dir, "old_dir"))

    @mock.patch("backend.actions.uses_devel_repo")
    def test_delete_no_chroot_dirs(self, mc_devel, mc_time):
        mc_devel.return_value = False
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "id": 7,
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "data": self.ext_data_for_delete_build,
            },

        )
        result = test_action.run()
        assert result.result == ActionResult.FAILURE

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (0, "", "")
        # mc_createrepo.side_effect = IOError()

        tmp_dir = self.make_temp_dir()

        chroot_1_dir = os.path.join(tmp_dir, "old_dir", "fedora20")
        os.mkdir(chroot_1_dir)
        foo_pkg_dir = os.path.join(chroot_1_dir, "foo")
        os.mkdir(foo_pkg_dir)
        chroot_2_dir = os.path.join(tmp_dir, "old_dir", "epel7")
        os.mkdir(chroot_2_dir)

        with open(os.path.join(chroot_1_dir, "foo", "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        log_path = os.path.join(chroot_1_dir, "build-42.log")
        with open(log_path, "w") as fh:
            fh.write(self.test_content)

        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42
            },
            frontend_client=mc_front_cb,
        )

        assert os.path.exists(foo_pkg_dir)
        test_action.run()
        assert not os.path.exists(foo_pkg_dir)
        assert not os.path.exists(log_path)
        assert os.path.exists(chroot_1_dir)
        assert os.path.exists(chroot_2_dir)

        create_repo_expected_call = mock.call(
            username=u'foo',
            projectname=u'bar',
            base_url=u'http://example.com/results/foo/bar/fedora20',
            path='{}/old_dir/fedora20'.format(self.tmp_dir_name),
            front_url=None
        )
        assert mc_createrepo.call_args == create_repo_expected_call

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded_createrepo_error(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (1, "", "Create repo failed")
        # mc_createrepo.side_effect = IOError()

        tmp_dir = self.make_temp_dir()

        chroot_1_dir = os.path.join(tmp_dir, "old_dir", "fedora20")
        os.mkdir(chroot_1_dir)
        foo_pkg_dir = os.path.join(chroot_1_dir, "foo")
        os.mkdir(foo_pkg_dir)
        chroot_2_dir = os.path.join(tmp_dir, "old_dir", "epel7")
        os.mkdir(chroot_2_dir)

        with open(os.path.join(chroot_1_dir, "foo", "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42,
            },
            frontend_client=mc_front_cb,
        )

        test_action.run()

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_delete_two_chroots(self, mc_createrepo, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796

        """
        mc_createrepo.return_value = 0, STDOUT, ""

        resource_name = "1171796.tar.gz"
        self.unpack_resource(resource_name)

        chroot_20_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-x86_64")

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        self.opts.destdir = self.tmp_dir_name
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "src_pkg_name": "rubygem-log4r-1.1.10-2.fc21",
                    "username": "foo",
                    "projectname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert not os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert not os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_delete_two_chroots_two_remains(self, mc_createrepo, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796
        extended: we also put two more chroots, which should be unaffected
        """
        mc_createrepo.return_value = 0, STDOUT, ""

        resource_name = "1171796_doubled.tar.gz"
        self.unpack_resource(resource_name)

        chroot_20_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-x86_64")
        chroot_20_i386_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-i386")
        chroot_21_i386_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-i386")

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.log"))

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.rsync.log"))

        assert os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_20_i386_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_i386_path, "rubygem-log4r-1.1.10-2.fc21"))

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        self.opts.destdir = self.tmp_dir_name
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "src_pkg_name": "rubygem-log4r-1.1.10-2.fc21",
                    "username": "foo",
                    "projectname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
            frontend_client=mc_front_cb
        )
        test_action.run()

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.log"))

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.rsync.log"))

        assert not os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert not os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_20_i386_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_i386_path, "rubygem-log4r-1.1.10-2.fc21"))

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_delete_build_with_bad_pkg_name(self, mc_createrepo, mc_time):
        """
        regression: https://bugzilla.redhat.com/show_bug.cgi?id=1203753

        """
        mc_time.time.return_value = self.test_time

        resource_name = "1171796_doubled.tar.gz"
        self.unpack_resource(resource_name)

        chroot_20_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-x86_64")

        mc_createrepo.return_value = 0, STDOUT, ""
        mc_front_cb = MagicMock()
        self.opts.destdir = self.tmp_dir_name
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "src_pkg_name": "",
                    "username": "foo",
                    "projectname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
            frontend_client=mc_front_cb,
        )

        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)
        test_action.run()
        # shouldn't touch chroot dirs
        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)

    @mock.patch("backend.actions.uses_devel_repo")
    def test_delete_multiple_builds_succeeded(self, mc_build_devel, mc_time):
        mc_time.time.return_value = self.test_time
        mc_build_devel.return_value = False

        tmp_dir = self.make_temp_dir()

        chroot_dir = os.path.join(tmp_dir, "foo", "bar", "fedora-20")
        os.makedirs(chroot_dir)
        pkg_build_1_dir = os.path.join(chroot_dir, "01-foo")
        pkg_build_2_dir = os.path.join(chroot_dir, "02-foo")
        pkg_build_3_dir = os.path.join(chroot_dir, "03-foo")
        os.mkdir(pkg_build_1_dir)
        os.mkdir(pkg_build_2_dir)
        os.mkdir(pkg_build_3_dir)

        ext_data = json.dumps({
            "ownername": "foo",
            "projectname": "bar",
            "project_dirnames": {
                'bar': {
                    "fedora-20": ["01-foo", "02-foo"],
                }
            },
        })

        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "builds",
                "id": 7,
                "data": ext_data,
            },
        )

        assert os.path.exists(pkg_build_1_dir)
        assert os.path.exists(pkg_build_2_dir)
        test_action.run()
        assert not os.path.exists(pkg_build_1_dir)
        assert not os.path.exists(pkg_build_2_dir)
        assert os.path.exists(chroot_dir)
        assert os.path.exists(pkg_build_3_dir)

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_handle_createrepo_ok(self, mc_createrepo, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo.return_value = 0, STDOUT, ""

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        self.opts.destdir=tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 8
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 8
        assert result_dict["result"] == ActionResult.SUCCESS

        exp_call_1 = mock.call(path=tmp_dir + u'/foo/bar/epel-6-i386',
                               front_url=self.opts.frontend_base_url, override_acr_flag=True,
                               username=u"foo", projectname=u"bar")
        exp_call_2 = mock.call(path=tmp_dir + u'/foo/bar/fedora-20-x86_64',
                               front_url=self.opts.frontend_base_url, override_acr_flag=True,
                               username=u"foo", projectname=u"bar")
        assert exp_call_1 in mc_createrepo.call_args_list
        assert exp_call_2 in mc_createrepo.call_args_list
        assert len(mc_createrepo.call_args_list) == 2

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_handle_createrepo_failure_1(self, mc_createrepo, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo.side_effect = CreateRepoError("test exception", ["foo", "bar"], 1)
        # return_value = 1, STDOUT, ""

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 9
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 9
        assert result_dict["result"] == ActionResult.FAILURE

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.createrepo")
    def test_handle_createrepo_failure_3(self, mc_createrepo, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo.side_effect = [
            STDOUT,
            CreateRepoError("test exception", ["foo", "bar"], 1),
        ]

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        self.opts.destdir = tmp_dir
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 10
            },
            frontend_client=mc_front_cb,
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 10
        assert result_dict["result"] == ActionResult.FAILURE

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("backend.actions.create_user_keys")
    def test_handle_generate_gpg_key(self, mc_cuk, mc_time):
        uname = "foo"
        pname = "bar"
        action_data = json.dumps({
            "username": uname,
            "projectname": pname,
        })

        expected_call = mock.call(uname, pname, self.opts)

        mc_front_cb = MagicMock()
        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.GEN_GPG_KEY,
                "data": action_data,
                "id": 11
            },
            frontend_client=mc_front_cb
        )

        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 11
        assert result_dict["result"] == ActionResult.SUCCESS

        assert mc_cuk.call_args == expected_call

        # handle exception
        mc_cuk.side_effect = CoprKeygenRequestError("foo")
        mc_front_cb.reset_mock()
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 11
        assert result_dict["result"] == ActionResult.FAILURE

        # test, that key creation is skipped when signing is disabled
        self.opts.do_sign = False
        mc_front_cb.reset_mock()
        mc_cuk.reset_mock()
        test_action.run()

        assert not mc_cuk.called
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 11
        assert result_dict["result"] == ActionResult.SUCCESS

    @unittest.skip("Fixme, test doesn't work.")
    def test_request_exception_is_taken_care_of_when_posting_to_frontend(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_frontend_client = MagicMock()
        mc_frontend_client.update = MagicMock(side_effect=RequestException)

        tmp_dir = self.make_temp_dir()
        self.opts.destdir = os.path.join(tmp_dir, "dir-not-exists")

        test_action = Action(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                "old_value": "old_dir",
            },
            frontend_client=mc_frontend_client,
        )

        try:
            test_action.run()
        except Exception as e:
            assert False
