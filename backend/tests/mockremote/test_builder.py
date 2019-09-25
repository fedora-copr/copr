# coding: utf-8
import copy

from collections import defaultdict
from pprint import pprint
import socket
from munch import Munch
from backend.exceptions import BuilderError, VmError

import tempfile
import shutil
import os

from backend.job import BuildJob

from unittest import mock, skip
from unittest.mock import patch, MagicMock
import pytest
from types import MethodType

import backend.mockremote.builder as builder_module
from backend.mockremote.builder import Builder

MODULE_REF = "backend.mockremote.builder"

# TODO: drop these, these are not needed
class BuilderTimeOutError(Exception):
    pass
class AnsibleCallError(Exception):
    pass
class AnsibleResponseError(Exception):
    pass


@pytest.yield_fixture
def mc_socket():
    yield object()


def noop(*args, **kwargs):
    pass


def print_all(*args, **kwargs):
    pprint(args)
    pprint(kwargs)


STDOUT = "stdout"
STDERR = "stderr"
COPR_OWNER = "copr_owner"
COPR_NAME = "copr_name"
COPR_VENDOR = "vendor"


class TestBuilder(object):
    BUILDER_BUILDROOT_PKGS = []
    BUILDER_CHROOT = "fedora-20-i386"
    BUILDER_TIMEOUT = 1024
    BUILDER_HOSTNAME = "example.com"
    BUILDER_USER = "copr_builder"
    BUILDER_REMOTE_BASEDIR = "/tmp/copr-backend-test"
    BUILDER_REMOTE_TMPDIR = "/tmp/copr-backend-test-tmp"
    BUILDER_PKG_NAME = "foovar"
    BUILDER_PKG_BASE = "foovar-2.41.f21"
    BUILDER_PKG_VERSION = "2.41.f21"
    BUILDER_PKG = "http://example.com/foovar-2.41.f21.src.rpm"

    BUILD_REMOTE_TARGET = "/tmp/copr-backend-test/foovar-2.41.f21.src.rpm"

    STDOUT = "stdout"
    STDERR = "stderr"

    RESULT_DIR = "/tmp"
    opts = Munch(
        ssh=Munch(
            transport="paramiko"
        ),
        build_user=BUILDER_USER,
        timeout=BUILDER_TIMEOUT,
        remote_basedir=BUILDER_REMOTE_BASEDIR,
        remote_tempdir=BUILDER_REMOTE_TMPDIR,
        results_baseurl="http://example.com",

        redis_db=9,
        redis_port=7777,
    )

    GIT_HASH = "1234r"
    GIT_BRANCH = "f20"
    GIT_REPO = "foo/bar/xyz"

    def get_test_builder(self):
        self.job = BuildJob({
            "project_owner": COPR_OWNER,
            "project_name": COPR_NAME,
            "pkgs": self.BUILDER_PKG,
            "repos": "",
            "build_id": 12345,
            "chroot": self.BUILDER_CHROOT,
            "buildroot_pkgs": self.BUILDER_BUILDROOT_PKGS,

            "git_repo": self.GIT_REPO,
            "git_hash": self.GIT_HASH,
            "git_branch": self.GIT_BRANCH,

            "package_name": self.BUILDER_PKG_NAME,
            "package_version": self.BUILDER_PKG_VERSION
        }, Munch({
            "timeout": 1800,
            "destdir": self.test_root_path,
            "results_baseurl": "/tmp",
        }))

        self.mc_logger = MagicMock()
        builder = Builder(
            opts=self.opts,
            hostname=self.BUILDER_HOSTNAME,
            job=self.job,
            logger=self.mc_logger
        )
        builder.checked = True

        builder.remote_pkg_name = self.BUILDER_PKG_BASE
        builder.remote_pkg_path = os.path.join(self.BUILDER_REMOTE_BASEDIR, self.BUILDER_PKG_BASE + ".src.rpm")

        return builder

    def setup_method(self, method):
        self.test_root_path = tempfile.mkdtemp()
        self.stage = 0
        self.stage_ctx = defaultdict(dict)

    @property
    def buildcmd(self):
        return self.gen_mockchain_command(self.BUILDER_PKG)

    def teardown_method(self, method):
        if os.path.exists(self.test_root_path):
            shutil.rmtree(self.test_root_path)

    @skip("Fixme or remove, test doesn't work.")
    def test_constructor(self):
        builder = self.get_test_builder()
        assert builder.conn.remote_user == self.BUILDER_USER
        assert builder.root_conn.remote_user == "root"

    @skip("Fixme or remove, test doesn't work.")
    def test_get_remote_pkg_dir(self):
        builder = self.get_test_builder()
        expected = "/".join([self.BUILDER_REMOTE_TMPDIR, "build", "results",
                             self.BUILDER_CHROOT, builder.remote_pkg_name])
        assert builder._get_remote_results_dir() == expected

    @skip("Fixme or remove, test doesn't work.")
    def test_run_ansible(self):
        builder = self.get_test_builder()
        ans_cmd = "foo bar"

        for conn, as_root in [(builder.conn, False), (builder.root_conn, True)]:
            for module_name in [None, "foo", "copy"]:
                run_count = conn.run.call_count
                builder._run_ansible(ans_cmd, as_root=as_root)
                assert conn.run.call_count == run_count + 1
                assert conn.module_args == ans_cmd
                assert conn.module_name == module_name or "shell"

    @skip("Fixme or remove, test doesn't work.")
    def test_check_for_ans_answer(self):
        """
            Silly test. Ansible api has almost no documentation,
            so we can only cover some return patterns :(

        """
        tested_func = builder_module.check_for_ans_error

        cases = [
            {
                "args": [
                    {
                        "dark": {},
                        "contacted": {}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": None,
                "expected_exception": VmError
            },
            {
                "args": [
                    {
                        "dark": {self.BUILDER_HOSTNAME: ""},
                        "contacted": {}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": None,
                "expected_exception": VmError
            },
            {
                "args": [
                    {
                        "dark": {},
                        "contacted": {self.BUILDER_HOSTNAME: {
                            "rc": 0,
                            "stdout": "stdout",
                            "stderr": "stderr",
                            "stdother": "stdother",
                        }}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": None,
                "expected_exception": None
            },
            {
                "args": [
                    {
                        "dark": {},
                        "contacted": {self.BUILDER_HOSTNAME: {
                            "rc": 1,
                            "stdout": "stdout",
                            "stderr": "stderr",
                            "stdother": "stdother",
                        }}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": None,
                "expected_exception": AnsibleResponseError
            },
            {  # 5
                "args": [
                    {
                        "dark": {},
                        "contacted": {self.BUILDER_HOSTNAME: {
                            "rc": 1,
                            "stdout": "stdout",
                            "stderr": "stderr",
                            "stdother": "stdother",

                        }}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {"success_codes": [0, 1]},
                "expected_return": None,
                "expected_exception": None,
            },
            {
                "args": [
                    {
                        "dark": {},
                        "contacted": {self.BUILDER_HOSTNAME: {
                            "rc": 2,
                            "stdout": "stdout",
                            "stderr": "stderr",
                        }}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {"err_codes": [2, 3]},
                "expected_return": None,
                "expected_exception": AnsibleResponseError
            },
            {
                "args": [
                    {
                        "dark": {},
                        "contacted": {self.BUILDER_HOSTNAME: {
                            "failed": True,
                            "stdout": "stdout",
                            "stderr": "stderr",
                            "stdother": "stdother",
                        }}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": None,
                "expected_exception": AnsibleResponseError
            }
        ]
        # counter = 0
        for case in cases:
            if case["expected_exception"]:
                with pytest.raises(case["expected_exception"]):
                    tested_func(*case["args"], **case["kwargs"])
            else:
                result = tested_func(*case["args"], **case["kwargs"])
                assert result == case["expected_return"]

            # counter += 1
            # print("\nCounter {} passed".format(counter))

    @skip("Fixme or remove, test doesn't work.")
    def test_get_ans_results(self):
        result_obj = "RESULT_STRING"
        results = {"dark": {self.BUILDER_HOSTNAME: result_obj}, "contacted": {}}
        assert result_obj == builder_module.get_ans_results(results, self.BUILDER_HOSTNAME)

        results = {"contacted": {self.BUILDER_HOSTNAME: result_obj}, "dark": {}}
        assert result_obj == builder_module.get_ans_results(results, self.BUILDER_HOSTNAME)

        results = {"contacted": {self.BUILDER_HOSTNAME: "wrong_obj"},
                   "dark": {self.BUILDER_HOSTNAME: result_obj}}
        assert result_obj == builder_module.get_ans_results(results, self.BUILDER_HOSTNAME)

        results = {"contacted": {}, "dark": {}}
        assert {} == builder_module.get_ans_results(results, self.BUILDER_HOSTNAME)

    @skip("Fixme or remove, test doesn't work.")
    def test_check_hostname_check(self, mc_socket):
        mc_socket.gethostbyname.side_effect = socket.gaierror()
        builder = self.get_test_builder()
        for name in ["*", "256.0.0.1"]:
            with pytest.raises(BuilderError):
                builder.checked = False
                builder.hostname = name
                builder.check()

    @skip("Fixme or remove, test doesn't work.")
    def test_check_missing_required_binaries(self, mc_socket):
        builder = self.get_test_builder()
        self.stage = 0

        def ans_run():
            self.stage_ctx[self.stage]["conn"] = copy.deepcopy(builder.conn)
            ret_map = {
                0: {"contacted": {self.BUILDER_HOSTNAME: {"rc": 1, }}},
                1: {"contacted": {self.BUILDER_HOSTNAME: {"rc": 0, }}}
            }
            self.stage += 1
            return ret_map[self.stage - 1]

        builder.conn.run.side_effect = ans_run
        with pytest.raises(BuilderError) as err:
            builder.check()

        # import ipdb; ipdb.set_trace()
        # pprint(self.stage_ctx)
        assert "/bin/rpm -q mock rsync" in self.stage_ctx[0]["conn"].module_args

        assert "does not have mock or rsync installed" in err.value.msg

    @skip("Fixme or remove, test doesn't work.")
    def test_check_missing_mockchain_or_mock_config(self, mc_socket):
        builder = self.get_test_builder()

        def ans_run():
            self.stage_ctx[self.stage]["conn"] = copy.deepcopy(builder.conn)
            ret_map = {
                0: {"contacted": {self.BUILDER_HOSTNAME: {"rc": 0, }}},
                1: {"contacted": {self.BUILDER_HOSTNAME: {"rc": 1, }}}
            }
            self.stage += 1
            return ret_map[self.stage - 1]

        builder.conn.run.side_effect = ans_run
        with pytest.raises(BuilderError) as err:
            builder.check()

        # pprint(self.stage_ctx)
        assert "/usr/bin/test -f /usr/bin/mockchain" in self.stage_ctx[1]["conn"].module_args
        # assert "/usr/bin/test -f /etc/mock/{}.cfg".format(self.BUILDER_CHROOT) in \
        #        self.stage_ctx[1]["conn"].module_args

        assert "missing mockchain binary" in err.value.msg

    @skip("Fixme or remove, test doesn't work.")
    def test_check_missing_mock_config(self, mc_socket):
        builder = self.get_test_builder()

        ret_map = {
            0: {"contacted": {self.BUILDER_HOSTNAME: {"rc": "0", }}},
            1: {"contacted": {self.BUILDER_HOSTNAME: {"rc": "0", }}},
            2: {"contacted": {self.BUILDER_HOSTNAME: {"failed": "fatal_2", }}}
        }

        def ans_run():
            self.stage_ctx[self.stage]["conn"] = copy.deepcopy(builder.conn)
            self.stage += 1
            return ret_map[self.stage - 1]

        builder.conn.run.side_effect = ans_run
        with pytest.raises(BuilderError) as err:
            builder.check()

        # pprint(self.stage_ctx)
        assert "/usr/bin/test -f /usr/bin/mockchain" in self.stage_ctx[1]["conn"].module_args
        assert "/usr/bin/test -f /etc/mock/{}.cfg".format(self.BUILDER_CHROOT) in \
               self.stage_ctx[2]["conn"].module_args

        assert "missing mock config for chroot" in err.value.msg

    @skip("Fixme or remove, test doesn't work.")
    def test_tempdir_nop_when_provided(self):
        builder = self.get_test_builder()
        assert builder.tempdir == self.BUILDER_REMOTE_TMPDIR
        assert not builder.conn.run.called

    @skip("Fixme or remove, test doesn't work.")
    def test_tempdir_failed_to_create(self):
        builder = self.get_test_builder()
        builder._remote_tempdir = None

        builder.conn.run.return_value = {"contacted": {
            self.BUILDER_HOSTNAME: {"failed": "fatal_1", "stdout": None}}}

        with pytest.raises(BuilderError) as err:
            x = builder.tempdir

    @skip("Fixme or remove, test doesn't work.")
    def test_tempdir_correct_creation(self):
        builder = self.get_test_builder()
        builder._remote_tempdir = None

        new_tmp_dir = "/tmp/new/"

        def ans_run():
            self.stage_ctx[self.stage]["conn"] = copy.deepcopy(builder.conn)
            ret_map = {
                0: {"contacted": {
                    self.BUILDER_HOSTNAME: {"rc": 0, "stdout": new_tmp_dir}}},
                1: {"contacted": {
                    self.BUILDER_HOSTNAME: {"rc": 0}}},
            }
            self.stage += 1
            return ret_map[self.stage - 1]

        builder.conn.run.side_effect = ans_run
        x = builder.tempdir
        assert x == new_tmp_dir
        assert "/bin/mktemp -d {0}".format(self.BUILDER_REMOTE_BASEDIR) in \
               self.stage_ctx[0]["conn"].module_args

        assert "/bin/chmod 755 {}".format(new_tmp_dir) in \
               self.stage_ctx[1]["conn"].module_args

    @skip("Fixme or remove, test doesn't work.")
    def test_tempdir_setter(self):
        builder = self.get_test_builder()
        builder._remote_tempdir = None
        new_tmp_dir = "/tmp/new/"
        builder.tempdir = new_tmp_dir
        assert builder.tempdir == new_tmp_dir

    @skip("Fixme or remove, test doesn't work.")
    def test_modify_base_buildroot_malicious_vars(self):
        builder = self.get_test_builder()

        for bad_pkg in [
            "../'HOME-example.src.pkg",
            # FIXME: i'm assuming that the following should also cause error
            # "~HOM/E-example.src.pkg; rm -rf",
            # "../%HOME-example.src.pkg",
            # "../%HOME-example.src.pkg"

        ]:
            with pytest.raises(BuilderError) as err:
                builder.buildroot_pkgs = bad_pkg
                builder.modify_mock_chroot_config()

    @skip("Fixme or remove, test doesn't work.")
    def test_modify_chroot_disable_networking(self):
        storage = []

        def fake_run_ansible(self, cmd, *args, **kwargs):
            storage.append(cmd)

        builder = self.get_test_builder()
        builder.run_ansible_with_check = MethodType(fake_run_ansible, builder)
        builder.root_conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0, "stdout": None}},
            "dark": {}
        }

        self.job.enable_net = False
        # net should be disabled
        builder.modify_mock_chroot_config()

        expected = (
            'dest=/etc/mock/fedora-20-i386.cfg '
            'line="config_opts[\'use_host_resolv\'] = False" '
            'regexp="^.*user_host_resolv.*$"')
        assert any([expected in r for r in storage])

    @skip("Fixme or remove, test doesn't work.")
    def test_collect_build_packages(self):
        builder = self.get_test_builder()
        stdout = "stdout"

        builder.conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0, "stdout": stdout}},
            "dark": {}
        }
        builder.collect_built_packages()
        expected = (
            "cd {} && "
            "for f in `ls *.rpm |grep -v \"src.rpm$\"`; do"
            "   rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(builder._get_remote_results_dir())
        )
        assert builder.conn.module_args == expected

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.check_for_ans_error")
    def test_run_ansible_with_check(self, mc_check_for_ans_errror):
        builder = self.get_test_builder()

        cmd = "cmd"
        module_name = "module_name"
        as_root = True

        err_codes = [1, 3, 7, ]
        success_codes = [0, 255]

        results = mock.MagicMock()

        err_results = mock.MagicMock()

        mc_check_for_ans_errror.return_value = (False, [])
        builder._run_ansible = mock.MagicMock()
        builder._run_ansible.return_value = results

        got_results = builder.run_ansible_with_check(
            cmd, module_name, as_root, err_codes, success_codes)

        assert results == got_results
        expected_call_run = mock.call(cmd, module_name, as_root)
        assert expected_call_run == builder._run_ansible.call_args
        expected_call_check = mock.call(results, builder.hostname,
                                        err_codes, success_codes)
        assert expected_call_check == mc_check_for_ans_errror.call_args

        mc_check_for_ans_errror.side_effect = AnsibleResponseError(msg="err message", **err_results)

        with pytest.raises(AnsibleCallError):
            builder.run_ansible_with_check(
                cmd, module_name, as_root, err_codes, success_codes)



    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.check_for_ans_error")
    def test_check_build_success(self, mc_check_for_ans_errror):
        builder = self.get_test_builder()

        builder.check_build_success()

        expected_ans_args = (
            "/usr/bin/test -f "
            "/tmp/copr-backend-test-tmp/build/results/"
            "{}/{}/success"
        ).format(self.BUILDER_CHROOT, self.BUILDER_PKG_BASE)
        assert expected_ans_args == builder.conn.module_args

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.check_for_ans_error")
    def test_check_build_exception(self, mc_check_for_ans_errror):
        builder = self.get_test_builder()

        mc_check_for_ans_errror.side_effect = AnsibleResponseError(msg="err msg")

        with pytest.raises(BuilderError):
            builder.check_build_success()

        expected_ans_args = (
            "/usr/bin/test -f "
            "/tmp/copr-backend-test-tmp/build/results/"
            "{}/{}/success"
        ).format(self.BUILDER_CHROOT, self.BUILDER_PKG_BASE)
        assert expected_ans_args == builder.conn.module_args

    @skip("Fixme or remove, test doesn't work.")
    def test_get_mockchain_command(self):
        builder = self.get_test_builder()

        builder.job.repos = [
            "http://example.com/rhel7",
            "http://example.com/fedora-20; rm -rf",
            "http://example.com/fedora-$releasever",
            "http://example.com/fedora-rawhide",
        ]
        result_cmd = builder.gen_mockchain_command()
        expected = (
            "/usr/bin/mockchain -r {chroot} -l /tmp/copr-backend-test-tmp/build/"
            " -a http://example.com/rhel7 -a 'http://example.com/fedora-20; rm -rf' "
            "-a 'http://example.com/fedora-$releasever' -a http://example.com/fedora-rawhide "
            "-a {results_baseurl}/{owner}/{copr}/{chroot} -a {results_baseurl}/{owner}/{copr}/{chroot}/devel "
            "-m '--define=copr_username {owner}' -m '--define=copr_projectname {copr}'"
            " -m '--define=vendor Fedora Project COPR ({owner}/{copr})'"
            " {build_target}").format(
                owner=self.job.project_owner,
                copr=self.job.project_name,
                chroot=self.job.chroot,
                build_target=self.BUILD_REMOTE_TARGET,
                results_baseurl=self.RESULT_DIR
        )
        assert result_cmd == expected

        # builder.chroot = "fedora-rawhide"
        # builder.repos = [
        #     "http://example.com/rhel7",
        #     "http://example.com/fedora-20; rm -rf",
        #     "http://example.com/fedora-$releasever",
        #     "http://example.com/fedora-rawhide",
        # ]
        # builder.macros = {
        #     "foo": "bar",
        #     "foo; rm -rf": "bar",
        #     "foo2": "bar; rm -rf"
        # }
        # result_cmd = builder.gen_mockchain_command(self.BUILDER_PKG)
        # expected = (
        #     "/usr/bin/mockchain -r fedora-rawhide -l /tmp/copr-backend-test-tmp/build/"
        #     " -a http://example.com/rhel7 -a 'http://example.com/fedora-20; rm -rf' "
        #     "-a http://example.com/fedora-rawhide -a http://example.com/fedora-rawhide "
        #     "-m '--define=foo bar' -m '--define=foo; rm -rf bar' -m '--define=foo2 bar; rm -rf'"
        #     " http://example.com/foovar-2.41.f21.src.rpm")
        # assert result_cmd == expected

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.time")
    def test_run_command_and_wait_timeout(self, mc_time):
        build_cmd = "foo bar"
        builder = self.get_test_builder()

        mc_poller = mock.MagicMock()
        mc_poller.poll.return_value = {"contacted": {}, "dark": {}}
        builder.conn.run_async.return_value = None, mc_poller
        builder.timeout = 50

        mc_time.return_value = None

        with pytest.raises(BuilderTimeOutError) as error:
            builder.run_build_and_wait(build_cmd)

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.time")
    def test_run_command_and_wait(self, mc_time):
        build_cmd = "foo bar"
        builder = self.get_test_builder()

        mc_poller = mock.MagicMock()
        builder.conn.run_async.return_value = None, mc_poller
        builder.timeout = 100

        expected_result = {"contacted": {self.BUILDER_HOSTNAME: True}, "dark": {}}

        def poll():
            if self.stage < 2:
                return {"contacted": {}, "dark": {}}
            else:
                return expected_result

        mc_poller.poll.side_effect = poll

        def incr_stage(*args, **kwargs):
            self.stage += 1

        mc_time.sleep.side_effect = incr_stage
        builder.run_build_and_wait(build_cmd)

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.Popen")
    def test_download(self, mc_popen):
        builder = self.get_test_builder()

        for ret_code, expected_success in [(0, True), (1, False), (23, False)]:
            mc_cmd = mock.MagicMock()
            mc_cmd.communicate.return_value = self.STDOUT, self.STDERR
            mc_cmd.returncode = ret_code
            mc_popen.return_value = mc_cmd
            if expected_success:
                builder.download("target_dir")
            else:
                with pytest.raises(BuilderError) as err:
                    builder.download("target_dir")
                assert err.value.return_code == ret_code
                # assert err.value.stderr == self.STDERR
                # assert err.value.stdout == self.STDOUT
            #
            # expected_arg = (
            #     "/usr/bin/rsync -avH -e 'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
            #     " copr_builder@example.com:/tmp/copr-backend-test-tmp/build/results/fedora-20-i386/foovar-2.41.f21 "
            #     "'/tmp/copr-backend-test'/ &> '/tmp/copr-backend-test'/build-00012345.rsync.log")
            #
            # assert mc_popen.call_args[0][0] == expected_arg

    @skip("Fixme or remove, test doesn't work.")
    @mock.patch("backend.mockremote.builder.Popen")
    def test_download_popen_error(self, mc_popen):
        builder = self.get_test_builder()
        mc_popen.side_effect = IOError()
        with pytest.raises(BuilderError):
            builder.download(self.RESULT_DIR)

    @skip("Fixme or remove, test doesn't work.")
    def test_build(self):
        builder = self.get_test_builder()
        builder.modify_mock_chroot_config = MagicMock()
        builder.check_if_pkg_local_or_http = MagicMock()
        builder.download_job_pkg_to_builder = MagicMock()
        builder.download_job_pkg_to_builder.return_value = "foobar"
        builder.check_if_pkg_local_or_http.return_value = self.BUILDER_PKG

        builder.run_build_and_wait = MagicMock()
        successful_wait_result = {
            "contacted": {self.BUILDER_HOSTNAME: {
                "rc": 0, "stdout": self.STDOUT, "stderr": self.STDERR
            }},
            "dark": {}
        }
        builder.run_build_and_wait.return_value = successful_wait_result

        builder.check_build_success = MagicMock()
        builder.check_build_success.return_value = (self.STDERR, False, self.STDOUT)

        builder.collect_built_packages = MagicMock()

        stdout = builder.build()
        assert stdout == self.STDOUT

        assert builder.modify_mock_chroot_config.called
        assert builder.run_build_and_wait.called
        assert builder.check_build_success.called
        assert builder.collect_built_packages

        # test providing version / obsolete
        builder.build()

        # test timeout handle
        builder.run_build_and_wait.side_effect = BuilderTimeOutError("msg")

        with pytest.raises(BuilderError) as error:
            builder.build()

        assert error.value.msg == "msg"

        # remove timeout
        builder.run_build_and_wait.side_effect = None
        builder.build()

        # error inside wait result
        unsuccessful_wait_result = {
            "contacted": {self.BUILDER_HOSTNAME: {
                "rc": 1, "stdout": self.STDOUT, "stderr": self.STDERR
            }},
            "dark": {}
        }
        builder.run_build_and_wait.return_value = unsuccessful_wait_result
        with pytest.raises(BuilderError):
            builder.build()

    @skip("Fixme or remove, test doesn't work.")
    def test_pre_process_repo_url(self):
        builder = self.get_test_builder()

        cases = [
            ("", "''"),
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/",
             "'http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/'"),
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/$chroot/",
             "http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/{}/".format(self.job.chroot)),
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/$distname-$releasever-$basearch/",
             "'http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/'"),
            ("copr://foo/bar",
             "{}/foo/bar/fedora-20-i386".format(self.opts.results_baseurl)),
        ]

        for input_url, expected in cases:
            assert builder.pre_process_repo_url(input_url) == expected

        self.job.chroot = "fedora-20-rawhide"
        cases = [
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/",
             "'http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/'"),
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/$chroot/",
             "http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/{}/".format(self.job.chroot)),
            ("http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/$distname-$releasever-$basearch/",
             "'http://copr-be.c.fp.org/results/rhughes/f20-gnome-3-12/fedora-$releasever-$basearch/'"),
        ]
        for input_url, expected in cases:
            expected = expected.replace("$releasever", "rawhide")
            assert builder.pre_process_repo_url(input_url) == expected

        with mock.patch("{}.urlparse".format(MODULE_REF)) as handle:
            handle.side_effect = IOError
            for input_url, _ in cases:
                assert builder.pre_process_repo_url(input_url) is None

    @skip("Fixme or remove, test doesn't work.")
    def test_check_pubsub_build_interruption(self):
        builder = self.get_test_builder()
        builder.callback = MagicMock()
        builder.ps = MagicMock()
        for val in [None, {}, {"foo": "bar"}, {"type": "subscribe"}]:
            builder.ps.get_message.return_value = val
            builder.check_pubsub()

        builder.ps.get_message.return_value = {"type": "message", "data": ""}
        with pytest.raises(VmError):
            builder.check_pubsub()

