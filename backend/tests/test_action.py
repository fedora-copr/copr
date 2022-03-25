import os
import json
import tempfile
import shutil
import time
import tarfile
import subprocess
from munch import Munch

import pytest
import httpretty

import unittest
from unittest import mock
from unittest.mock import MagicMock

from copr_backend.actions import Action, ActionType, ActionResult
from copr_backend.exceptions import CreateRepoError, CoprKeygenRequestError
from requests import RequestException

from testlib.repodata import load_primary_xml

RESULTS_ROOT_URL = "http://example.com/results"
STDOUT = "stdout"
STDERR = "stderr"


@mock.patch("copr_backend.actions.time")
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
            "appstream": True,
            "project_dirname": "bar",
            "chroot_builddirs": {
                "fedora20": ["00001-foo"],
                "epel7": ["00001-foo"],
            },
        })

        self.opts = Munch(
            redis_db=9,
            redis_port=7777,

            destdir="/var/lib/copr/public_html/results/",
            frontend_base_url="https://example.com",
            results_baseurl=RESULTS_ROOT_URL,

            do_sign=False,

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

        self.test_project_dir = os.path.join(self.tmp_dir_name, "foo", "bar")
        os.makedirs(self.test_project_dir)

        # nothing should ever delete these
        os.mkdir(os.path.join(self.tmp_dir_name, "foo", "old_dir"))
        os.mkdir(os.path.join(self.tmp_dir_name, "old_dir"))

        self.test_content = "time: {}\n".format(self.test_time)

        return self.tmp_dir_name

    def unpack_resource(self, resource_name):
        if self.tmp_dir_name is None:
            self.make_temp_dir()

        src_path = os.path.join(os.path.dirname(__file__),
                                "_resources", resource_name)

        extract_to = self.test_project_dir

        with tarfile.open(src_path, "r:gz") as tfile:
            tfile.extractall(self.test_project_dir)

        if resource_name == "testresults.tar.gz":
            # This tar.gz is inconsistently generated, but changing it would
            # only waste the git repo size.  NOTE! If you ever have to touch
            # this tarball, start distributing that tarball as separate
            # file/project and use it as Source1: in the spec file.
            testresults = os.path.join(self.test_project_dir, 'testresults')
            for subdir in os.listdir(testresults):
                shutil.move(os.path.join(testresults, subdir),
                            os.path.join(self.tmp_dir_name, subdir))
            self.test_project_dir = os.path.join(self.tmp_dir_name, '@copr', 'prunerepo')

    def test_action_run_legal_flag(self, mc_time):
        mc_time.time.return_value = self.test_time
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.LEGAL_FLAG,
                "id": 1
            },
        )
        test_action.run()

        self.dummy = str(test_action)

    @mock.patch("copr_backend.actions.copy_tree")
    @mock.patch("copr_backend.actions.os.path.exists")
    @mock.patch("copr_backend.actions.unsign_rpms_in_dir")
    @mock.patch("copr_backend.helpers.subprocess.Popen")
    def test_action_handle_forks(self, mc_popen, mc_unsign_rpms_in_dir,
                                 mc_exists, mc_copy_tree, mc_time):
        mc_popen.return_value.communicate.return_value = ("", "")
        mc_time.time.return_value = self.test_time
        mc_exists = True
        test_action = Action.create_from(
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
                        "copr": "source-copr",
                        "appstream": True,
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
        assert len(mc_popen.call_args_list) == 3

        dirs = set()
        for call in mc_popen.call_args_list:
            args = call[0][0]
            assert args[0] == 'copr-repo'
            dirs.add(args[2])

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
        test_action = Action.create_from(
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
        test_action = Action.create_from(
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
        test_action = Action.create_from(
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

    def test_action_run_delete_copr(self, mc_time):
        tmp_dir = self.make_temp_dir()
        self.opts.destdir = tmp_dir

        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                # baz doesn't exist
                "data": json.dumps({
                    "ownername": "foo",
                    "project_dirnames": ["bar", "baz"],
                    "appstream": True,
                }),
            },
        )

        assert os.path.exists(os.path.join(tmp_dir, "foo", "bar"))
        assert not os.path.exists(os.path.join(tmp_dir, "foo", "baz"))
        assert test_action.run() == ActionResult.SUCCESS
        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))
        assert not os.path.exists(os.path.join(tmp_dir, "foo", "bar"))

    @unittest.skip("Fixme, test doesn't work.")
    def test_action_run_delete_copr_remove_folders(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        self.opts.destdir=tmp_dir
        test_action = Action.create_from(
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

    @mock.patch("copr_backend.actions.uses_devel_repo")
    @mock.patch("copr_backend.actions.call_copr_repo")
    def test_delete_no_chroot_dirs(self, mc_call, mc_devel, mc_time):
        mc_devel.return_value = False
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        self.opts.destdir = tmp_dir
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "id": 1,
                "object_id": 1,
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "data": self.ext_data_for_delete_build,
            },

        )
        result = test_action.run()
        assert len(mc_call.call_args_list) == 0
        assert result == ActionResult.FAILURE

    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_build_succeeded(self, mc_devel, mc_time):
        mc_devel.return_value = False
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        proj_dir = os.path.join(tmp_dir, "foo", "bar")
        chroot_1_dir = os.path.join(proj_dir, "fedora20")
        chroot_2_dir = os.path.join(proj_dir, "epel7")
        foo_pkg_dir = os.path.join(chroot_1_dir, "00001-foo")

        os.makedirs(chroot_2_dir)
        os.makedirs(foo_pkg_dir)

        with open(os.path.join(foo_pkg_dir, "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        log_path = os.path.join(chroot_1_dir, "build-{:08d}.log".format(42))
        with open(log_path, "w") as fh:
            fh.write(self.test_content)

        self.opts.destdir = tmp_dir
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42
            },
        )

        assert os.path.exists(foo_pkg_dir)
        assert test_action.run() == ActionResult.SUCCESS
        assert not os.path.exists(foo_pkg_dir)
        assert not os.path.exists(log_path)
        assert os.path.exists(chroot_1_dir)
        assert os.path.exists(chroot_2_dir)

    @pytest.mark.parametrize('devel', [False, True])
    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_build_acr_reflected(self, mc_devel, mc_time, devel):
        """
        When build is deleted, we want to remove it from both devel and normal
        (production) repodata
        """
        mc_devel.return_value = devel
        self.unpack_resource("testresults.tar.gz")

        chroot = os.path.join(self.test_project_dir, 'fedora-23-x86_64')
        repodata = os.path.join(chroot, 'repodata')
        devel_dir = os.path.join(chroot, 'devel')
        repodata_devel = os.path.join(devel_dir, 'repodata')
        builddir = '00000049-example'
        assert os.path.exists(chroot)
        assert not os.path.exists(devel_dir)

        # create repodata under 'devel'
        assert subprocess.call(['copr-repo', chroot, '--devel']) == 0

        old_primary = load_primary_xml(repodata)
        old_primary_devel = load_primary_xml(repodata_devel)
        assert len(old_primary['names']) == 3 # noarch vs. src
        assert len(old_primary['hrefs']) == 5

        for package in old_primary_devel['packages']:
            assert old_primary_devel['packages'][package]['xml:base'] \
                   == 'https://example.com/results/@copr/prunerepo/fedora-23-x86_64'
            # clear it
            old_primary_devel['packages'][package]['xml:base'] = ''

        assert old_primary == old_primary_devel

        self.opts.destdir = self.tmp_dir_name

        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "object_id": 49,
                "old_value": "old_dir",
                "data": json.dumps({
                    "ownername": "@copr",
                    "projectname": "prunerepo",
                    "project_dirname": "prunerepo",
                    "appstream": True,
                    "chroot_builddirs": {
                        "fedora-23-x86_64": [builddir],
                    },
                }),
            },
        )

        assert test_action.run() == ActionResult.SUCCESS

        new_primary = load_primary_xml(repodata)
        new_primary_devel = load_primary_xml(repodata_devel)

        if devel:
            assert new_primary_devel['names'] == set(['prunerepo'])
            assert len(new_primary['names']) == 3
        else:
            assert new_primary['names'] == set(['prunerepo'])
            assert len(new_primary_devel['names']) == 3

    @mock.patch("copr_backend.actions.call_copr_repo")
    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_build_succeeded_createrepo_error(self, mc_devel,
                                                     mc_call_repo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_call_repo.return_value = 0
        tmp_dir = self.make_temp_dir()

        chroot_1_dir = os.path.join(tmp_dir, "foo", "bar", "fedora20")
        foo_pkg_dir = os.path.join(chroot_1_dir, "foo")
        os.makedirs(foo_pkg_dir)
        chroot_2_dir = os.path.join(tmp_dir, "foo", "bar", "epel7")
        os.mkdir(chroot_2_dir)

        with open(os.path.join(foo_pkg_dir, "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        self.opts.destdir = tmp_dir
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42,
            },
        )
        # just fail
        assert test_action.run() == ActionResult.FAILURE

    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_two_chroots(self, mc_devel, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796
        """
        mc_devel.return_value = 0
        self.unpack_resource("1171796.tar.gz")

        chroot_20_path = os.path.join(self.tmp_dir_name, "foo", "bar", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "foo", "bar", "fedora-21-x86_64")

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        for path in [chroot_20_path, chroot_21_path]:
            # the 1171796 tarball above contains too old directory structure,
            # for some time we prefix the ID with zeroes.  So create another
            # (newer variant of) log file and check that both logs would be
            # potentially removed.
            shutil.copy(os.path.join(path, "build-15.log"),
                        os.path.join(path, "build-00000015.log"))

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

        mc_time.time.return_value = self.test_time

        self.opts.destdir = self.tmp_dir_name
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "ownername": "foo",
                    "projectname": "bar",
                    "appstream": True,
                    "project_dirname": "bar",
                    "chroot_builddirs": {
                        "fedora-20-x86_64": ["rubygem-log4r-1.1.10-2.fc21"],
                        "fedora-21-x86_64": ["rubygem-log4r-1.1.10-2.fc21"],
                    }
                }),
            },
        )
        assert test_action.run() == ActionResult.SUCCESS

        assert not os.path.exists(os.path.join(chroot_20_path, "build-00000015.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-00000015.log"))
        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert not os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert not os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)

    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_two_chroots_two_remain(self, mc_devel, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796
        extended: we also put two more chroots, which should be unaffected
        """
        mc_devel.return_value = 0
        self.unpack_resource("1171796_doubled.tar.gz")

        subdir = os.path.join(self.tmp_dir_name, "foo", "bar")

        chroot_20_path = os.path.join(subdir, "fedora-20-x86_64")
        chroot_21_path = os.path.join(subdir, "fedora-21-x86_64")
        chroot_20_i386_path = os.path.join(subdir, "fedora-20-i386")
        chroot_21_i386_path = os.path.join(subdir, "fedora-21-i386")

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

        self.opts.destdir = self.tmp_dir_name
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "ownername": "foo",
                    "projectname": "bar",
                    "appstream": True,
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"],
                    "project_dirname": "bar",
                    "chroot_builddirs": {
                        "fedora-20-x86_64": ["rubygem-log4r-1.1.10-2.fc21"],
                        "fedora-21-x86_64": ["rubygem-log4r-1.1.10-2.fc21"],
                    }
                }),
            },
        )

        assert test_action.run() == ActionResult.SUCCESS

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

    def test_delete_build_with_bad_pkg_name(self, mc_time):
        """
        Originally written for regression:
        https://bugzilla.redhat.com/show_bug.cgi?id=1203753
        But we nowadays donjt send src_pkg_name at all.
        """
        mc_time.time.return_value = self.test_time

        self.unpack_resource("1171796_doubled.tar.gz")

        chroot_20_path = os.path.join(self.tmp_dir_name, "foo", "bar", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "foo", "bar", "fedora-21-x86_64")

        self.opts.destdir = self.tmp_dir_name
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "src_pkg_name": "",
                    "ownername": "foo",
                    "projectname": "bar",
                    "project_dirname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
        )

        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)
        result = test_action.run()
        assert result == ActionResult.FAILURE

        # shouldn't touch chroot dirs
        assert os.path.exists(chroot_20_path)
        assert os.path.exists(chroot_21_path)

    @mock.patch("copr_backend.actions.uses_devel_repo")
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
            "appstream": True,
            "project_dirnames": {
                'bar': {
                    "fedora-20": ["01-foo", "02-foo"],
                }
            },
            "build_ids": ['01', '02'],
        })

        self.opts.destdir = tmp_dir
        test_action = Action.create_from(
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

    # We want to test that ACR flag doesn't make any difference here, explicit
    # createrepo always works with non-devel directory.
    @pytest.mark.parametrize('devel', [False, True])
    @mock.patch("copr_backend.helpers.subprocess.Popen")
    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_handle_createrepo_ok(self, mc_devel, mc_sp_popen, mc_time, devel):
        mc_sp_popen.return_value.communicate.return_value = ("", "")
        mc_sp_popen.return_value.returncode = 0
        mc_devel.return_value = devel

        tmp_dir = self.make_temp_dir()

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "ownername": "foo",
            "projectname": "bar",
            "appstream": True,
            "project_dirnames": ["bar"],
            "devel": False,
        })
        self.opts.destdir = tmp_dir

        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 8
            },
        )
        assert test_action.run() == ActionResult.SUCCESS

        for chroot in ['fedora-20-x86_64', 'epel-6-i386']:
            cmd = ["copr-repo", "--batched",
                   os.path.join(self.test_project_dir, chroot)]
            exp_call = mock.call(cmd, stdout=-1, stderr=-1, shell=False, encoding='utf-8')
            assert exp_call in mc_sp_popen.call_args_list

        assert len(mc_sp_popen.call_args_list) == 2

    @mock.patch("copr_backend.actions.call_copr_repo")
    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_handle_createrepo_failure_1(self, mc_devel, mc_call, mc_time):
        tmp_dir = self.make_temp_dir()
        mc_call.return_value = 0 # failure

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "ownername": "foo",
            "projectname": "bar",
            "appstream": True,
            "project_dirnames": ["bar"],
            "devel": False,
        })
        self.opts.destdir = tmp_dir
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 9
            },
        )
        assert test_action.run() == ActionResult.FAILURE

    @unittest.skip("Fixme, test doesn't work.")
    @mock.patch("copr_backend.actions.create_user_keys")
    def test_handle_generate_gpg_key(self, mc_cuk, mc_time):
        uname = "foo"
        pname = "bar"
        action_data = json.dumps({
            "username": uname,
            "projectname": pname,
        })

        expected_call = mock.call(uname, pname, self.opts)

        mc_front_cb = MagicMock()
        test_action = Action.create_from(
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

        test_action = Action.create_from(
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

    @mock.patch("copr_backend.actions.uses_devel_repo")
    def test_delete_chroot(self, mc_devel, mc_time):
        mc_devel.return_value = False
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        proj_dir = os.path.join(tmp_dir, "foo", "bar")
        chroot_1_dir = os.path.join(proj_dir, "fedora20")
        chroot_2_dir = os.path.join(proj_dir, "epel7")
        foo_pkg_dir = os.path.join(chroot_1_dir, "00001-foo")

        os.makedirs(chroot_2_dir)
        os.makedirs(foo_pkg_dir)

        with open(os.path.join(foo_pkg_dir, "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        log_path = os.path.join(chroot_1_dir, "build-{:08d}.log".format(42))
        with open(log_path, "w") as fh:
            fh.write(self.test_content)
        self.opts.destdir = tmp_dir

        data = json.dumps({
            "ownername": "foo",
            "projectname": "bar",
            "chrootname": "fedora20",
        })
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.DELETE,
                "object_type": "chroot",
                "id": None,
                "old_value": None,
                "data": data,
                "object_id": None,
            },
        )

        assert os.path.exists(foo_pkg_dir)
        assert os.path.exists(chroot_1_dir)
        assert test_action.run() == ActionResult.SUCCESS
        assert not os.path.exists(foo_pkg_dir)
        assert not os.path.exists(chroot_1_dir)

        # The action shouldn't fail even when the directory doesn't exist anymore
        assert test_action.run() == ActionResult.SUCCESS

    @httpretty.activate()
    def test_comps_create(self, mc_time):
        _ = mc_time
        text = "some xml body\n"
        httpretty.register_uri(
            httpretty.GET,
            "https://example.com/comps/path/",
            body=text,
        )

        self.opts.destdir = self.make_temp_dir()
        action_dict = {
            "action_type": 4,
            "created_on": 1622632008,
            "data": json.dumps({
                "ownername": "praiskup",
                "projectname": "ping",
                "chroot": "fedora-rawhide-x86_64",
                "comps_present": True,
                "url_path": "/comps/path/",
            }),
            "id": 672272,
            "object_type": "copr_chroot",
            "object_id": None,
            "old_value": None,
            "priority": 0,
        }
        test_action = Action.create_from(
            opts=self.opts,
            action=action_dict,
        )
        assert test_action.run() == ActionResult.SUCCESS

        file = os.path.join(self.opts.destdir,
                            "praiskup/ping/fedora-rawhide-x86_64",
                            "comps.xml")
        with open(file, "r") as fd:
            lines = fd.readlines()
            assert lines == [text]

    @mock.patch("copr_backend.actions.shutil.rmtree")
    def test_remove_dirs(self, mock_rmtree, mc_time):
        _unused = mc_time
        test_action = Action.create_from(
            opts=self.opts,
            action={
                "action_type": ActionType.REMOVE_DIRS,
                "data": json.dumps([
                    "@python/python3.8:pr:11",
                    "jdoe/some:pr:123",
                ]),
            },
        )
        assert test_action.run() == ActionResult.SUCCESS
        assert mock_rmtree.call_args_list == [
            mock.call('/var/lib/copr/public_html/results/@python/python3.8:pr:11'),
            mock.call('/var/lib/copr/public_html/results/jdoe/some:pr:123'),
        ]
