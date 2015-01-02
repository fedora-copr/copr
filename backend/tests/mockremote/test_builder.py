# coding: utf-8
import copy

from collections import defaultdict
from pprint import pprint
from bunch import Bunch
from backend.exceptions import BuilderError, BuilderTimeOutError

import tempfile
import shutil
import os

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import patch, MagickMock
else:
    import mock
    from mock import patch, MagicMock

import pytest

import backend.mockremote.builder as builder_module
from backend.mockremote.builder import Builder

# @pytest.yield_fixture
# def mc_ansible_runner():
# patcher = mock.patch("backend.mockremote.builder.Runner")
# yield patcher.start()
# patcher.stop()


def noop(*args, **kwargs):
    pass


def print_all(*args, **kwargs):
    pprint(args)
    pprint(kwargs)


def assert_in_log(msg, log_list):
    assert any(msg in record for record in log_list)


class TestBuilder(object):
    BUILDER_BUILDROOT_PKGS = []
    BUILDER_CHROOT = "fedora-20-i386"
    BUILDER_TIMEOUT = 1024
    BUILDER_HOSTNAME = "example.com"
    BUILDER_USER = "copr_builder"
    BUILDER_REMOTE_BASEDIR = "/tmp/copr-backend-test"
    BUILDER_REMOTE_TMPDIR = "/tmp/copr-backend-test-tmp"
    BUILDER_PKG_BASE = "foovar-2.41.f21"
    BUILDER_PKG = "http://example.com/foovar-2.41.f21.src.rpm"

    STDOUT = "stdout"
    STDERR = "stderr"

    opts = Bunch(
        ssh=Bunch(
            transport="paramiko"
        )
    )

    def get_test_builder(self):
        builder = Builder(
            opts=self.opts,
            hostname=self.BUILDER_HOSTNAME,
            username=self.BUILDER_USER,
            timeout=self.BUILDER_TIMEOUT,
            chroot=self.BUILDER_CHROOT,
            buildroot_pkgs=self.BUILDER_BUILDROOT_PKGS,
            remote_basedir=self.BUILDER_REMOTE_BASEDIR,
            remote_tempdir=self.BUILDER_REMOTE_TMPDIR,
            callback=self.mc_callback,
        )
        builder.checked = True
        return builder

    def setup_method(self, method):
        self.mc_ansible_runner_patcher = mock.patch("backend.mockremote.builder.Runner")
        self.mc_ansible_runner = self.mc_ansible_runner_patcher.start()
        self.mc_ansible_runner.side_effect = lambda **kwargs: mock.MagicMock(**kwargs)

        self.test_root_path = tempfile.mkdtemp()

        self.mc_callback = mock.MagicMock()
        self._cb_log = []
        self.mc_callback.log.side_effect = lambda msg: self._cb_log.append(msg)

        self.stage = 0
        self.stage_ctx = defaultdict(dict)

    @property
    def buildcmd(self):
        return self.gen_mockchain_command(self.BUILDER_PKG)

    def teardown_method(self, method):
        self.mc_ansible_runner_patcher.stop()
        # remote tmp dir

        if os.path.exists(self.test_root_path):
            shutil.rmtree(self.test_root_path)

    def test_constructor(self):
        assert not self.mc_ansible_runner.called
        builder = self.get_test_builder()
        assert self.mc_ansible_runner.called

        assert builder.conn.remote_user == self.BUILDER_USER
        assert builder.root_conn.remote_user == "root"

    def test_get_remote_pkg_dir(self):
        builder = self.get_test_builder()
        for pkg_name, pkg_fixed in [
            ("copr-backend-1.46-1.git.33.5733924.fc20.src.rpm", "copr-backend-1.46-1.git.33.5733924.fc20"),
            ("/tmp/kf5-baloo-5.1.0.1-1.fc20.src.rpm", "kf5-baloo-5.1.0.1-1.fc20")
        ]:
            expected = "/".join([self.BUILDER_REMOTE_TMPDIR, "build", "results",
                                 self.BUILDER_CHROOT, pkg_fixed])
            assert builder._get_remote_pkg_dir(pkg_name) == expected

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
                "expected_return": (False, {}),
                "expected_exception": None
            },
            {
                "args": [
                    {
                        "dark": {self.BUILDER_HOSTNAME: ""},
                        "contacted": {}
                    }, self.BUILDER_HOSTNAME
                ],
                "kwargs": {},
                "expected_return": (
                    True,
                    {"msg": "Error: Could not contact/connect to {}.".format(self.BUILDER_HOSTNAME)}),
                "expected_exception": None
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
                "expected_return": (False, {"rc": 0}),
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
                "expected_return": (
                    True, {
                        "rc": 1,
                        "msg": "rc 1 not in success_codes",
                        "stdout": "stdout",
                        "stderr": "stderr",

                    }),
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
                "kwargs": {"success_codes": [0, 1]},
                "expected_return": (False, {"rc": 1}),
                "expected_exception": None
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
                "expected_return": (True, {"rc": 2, "msg": "rc 2 matched err_codes",
                                           "stdout": "stdout", "stderr": "stderr"}),
                "expected_exception": None
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
                "expected_return": (True, {"msg": "results included failed as true",
                                           "stdout": "stdout", "stderr": "stderr"}),
                "expected_exception": None
            }
        ]
        for case in cases:
            if case["expected_exception"]:
                with pytest.raises(case["expected_exception"]):
                    tested_func(*case["args"], **case["kwargs"])
            else:
                result = tested_func(*case["args"], **case["kwargs"])
                assert result == case["expected_return"]

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

    def test_check_not_repeated(self):
        builder = self.get_test_builder()
        assert builder.check() == (True, [])
        assert not builder.conn.called
        assert not builder.root_conn.called

    def test_check_hostname_check(self):
        builder = self.get_test_builder()
        for name in ["*", "256.0.0.1"]:
            with pytest.raises(BuilderError):
                builder.checked = False
                builder.hostname = name
                builder.check()

    def test_check_missing_required_binaries(self):
        builder = self.get_test_builder()

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
            builder.checked = False
            builder.check()

        # import ipdb; ipdb.set_trace()
        assert "/bin/rpm -q mock rsync" in self.stage_ctx[0]["conn"].module_args

        assert "does not have mock or rsync installed" in err.value.msg

    def test_check_missing_mockchain_or_mock_config(self):
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
            builder.checked = False
            builder.check()

        assert "/usr/bin/test -f /usr/bin/mockchain" in self.stage_ctx[1]["conn"].module_args
        assert "/usr/bin/test -f /etc/mock/{}.cfg".format(self.BUILDER_CHROOT) in \
               self.stage_ctx[1]["conn"].module_args

        assert "lacks mockchain binary or mock config for chroot " in \
               err.value.msg

    def test_check_missing_alt_err_messages(self):
        builder = self.get_test_builder()

        def ans_run():
            self.stage_ctx[self.stage]["conn"] = copy.deepcopy(builder.conn)
            ret_map = {
                0: {"contacted": {self.BUILDER_HOSTNAME: {"failed": "fatal_1", }}},
                1: {"contacted": {self.BUILDER_HOSTNAME: {"failed": "fatal_2", }}}
            }
            self.stage += 1
            return ret_map[self.stage - 1]

        builder.conn.run.side_effect = ans_run
        with pytest.raises(BuilderError) as err:
            builder.checked = False
            builder.check()

        assert "/usr/bin/test -f /usr/bin/mockchain" in self.stage_ctx[1]["conn"].module_args
        assert "/usr/bin/test -f /etc/mock/{}.cfg".format(self.BUILDER_CHROOT) in \
               self.stage_ctx[1]["conn"].module_args

        assert "results included failed as true" in err.value.msg

    def test_check_set_checked(self):
        builder = self.get_test_builder()

        builder.conn.run.return_value = {"contacted": {self.BUILDER_HOSTNAME: {"rc": 0, }}}
        builder.checked = False
        builder.check()
        assert builder.checked

    def test_tempdir_nop_when_provided(self):
        builder = self.get_test_builder()
        assert builder.tempdir == self.BUILDER_REMOTE_TMPDIR
        assert not builder.conn.run.called

    def test_tempdir_failed_to_create(self):
        builder = self.get_test_builder()
        builder._remote_tempdir = None

        builder.conn.run.return_value = {"contacted": {
            self.BUILDER_HOSTNAME: {"failed": "fatal_1", "stdout": None}}}

        with pytest.raises(BuilderError) as err:
            x = builder.tempdir

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

    def test_tempdir_setter(self):
        builder = self.get_test_builder()
        builder._remote_tempdir = None
        new_tmp_dir = "/tmp/new/"
        builder.tempdir = new_tmp_dir
        assert builder.tempdir == new_tmp_dir

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
                builder.modify_base_buildroot()

    def test_modify_base_buildroot_on_error(self, ):
        builder = self.get_test_builder()
        br_pkgs = "foo bar"
        builder.buildroot_pkgs = br_pkgs
        builder.root_conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 1, "stdout": None}},
            "dark": {}
        }

        builder.modify_base_buildroot()

        assert_in_log("putting {} into minimal buildroot of fedora-20-i386".format(br_pkgs),
                      self._cb_log)

        assert not builder.conn.run.called
        assert builder.root_conn.run.called

        expected = (
            "dest=/etc/mock/{}.cfg "
            "line=\"config_opts['chroot_setup_cmd'] = 'install @buildsys-build {}'\" "
            "regexp=\"^.*chroot_setup_cmd.*$\""
        ).format(self.BUILDER_CHROOT, br_pkgs)
        assert builder.root_conn.module_args == expected

        assert_in_log("Error: ", self._cb_log[1:])

    def test_modify_base_buildroot(self, ):
        builder = self.get_test_builder()
        br_pkgs = "foo bar"
        builder.buildroot_pkgs = br_pkgs
        builder.root_conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0, "stdout": None}},
            "dark": {}
        }

        builder.modify_base_buildroot()

        assert_in_log("putting {} into minimal buildroot of fedora-20-i386".format(br_pkgs),
                      self._cb_log)

        assert not builder.conn.run.called
        assert builder.root_conn.run.called

        expected = (
            "dest=/etc/mock/{}.cfg "
            "line=\"config_opts['chroot_setup_cmd'] = 'install @buildsys-build {}'\" "
            "regexp=\"^.*chroot_setup_cmd.*$\""
        ).format(self.BUILDER_CHROOT, br_pkgs)
        assert builder.root_conn.module_args == expected

    def test_collect_build_packages(self):
        builder = self.get_test_builder()

        bd = {}
        stdout = "stdout"

        builder.conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0, "stdout": stdout}},
            "dark": {}
        }
        builder.collect_built_packages(bd, self.BUILDER_PKG)
        expected = (
            "cd {} && "
            "for f in `ls *.rpm |grep -v \"src.rpm$\"`; do"
            "   rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(builder._get_remote_pkg_dir(self.BUILDER_PKG_BASE))
        )
        assert builder.conn.module_args == expected

    @mock.patch("backend.mockremote.builder.check_for_ans_error")
    def test_check_build_success(self, mc_check_for_ans_errror):
        builder = self.get_test_builder()

        mc_check_for_ans_errror.return_value = "is_err", "err_results"

        results = builder.check_build_success(self.BUILDER_PKG, {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0,
                                                  "stdout": "stdout",
                                                  "stderr": "stderr"}},
            "dark": {}
        })

        assert ("stderr", "is_err", "stdout") == results

        expected_ans_args = (
            "/usr/bin/test -f "
            "/tmp/copr-backend-test-tmp/build/results/"
            "{}/{}/success"
        ).format(self.BUILDER_CHROOT, self.BUILDER_PKG_BASE)
        assert expected_ans_args == builder.conn.module_args

    def test_check_if_pkg_local_or_http_local(self):
        pkg_path = os.path.join(self.test_root_path, "{}.src.rpm".format(self.BUILDER_PKG_BASE))
        with open(pkg_path, "w") as handle:
            handle.write("1")

        builder = self.get_test_builder()
        dest = builder.check_if_pkg_local_or_http(pkg_path)
        dest_expected = os.path.join(self.BUILDER_REMOTE_TMPDIR, "{}.src.rpm".format(self.BUILDER_PKG_BASE))
        assert dest == dest_expected
        assert builder.conn.module_args == "src={} dest={}".format(pkg_path, dest_expected)
        assert builder.conn.module_name == "copy"

    def test_check_if_pkg_local_or_http_remote(self):
        builder = self.get_test_builder()
        dest = builder.check_if_pkg_local_or_http(self.BUILDER_PKG)

        assert dest == self.BUILDER_PKG

    def test_get_package_version(self):
        # TODO: pathc run_ansible with local cmd execution and put a real .src.rpm
        builder = self.get_test_builder()

        builder.conn.run.return_value = {
            "contacted": {self.BUILDER_HOSTNAME: {"rc": 0,
                                                  "stdout": "stdout",
                                                  "stderr": "stderr"}},
            "dark": {}
        }

        assert "stdout" == builder.get_package_version(self.BUILDER_PKG_BASE + ".src.rpm")
        assert builder.conn.module_args == "rpm -qp --qf \"%{{VERSION}}\" {}.src.rpm".format(self.BUILDER_PKG_BASE)

    def test_get_package_version_not_contacted(self):
        # TODO: pathc run_ansible with local cmd execution and put a real .src.rpm
        builder = self.get_test_builder()

        builder.conn.run.return_value = {}

        assert builder.get_package_version(self.BUILDER_PKG_BASE + ".src.rpm") is None
        assert builder.conn.module_args == "rpm -qp --qf \"%{{VERSION}}\" {}.src.rpm".format(self.BUILDER_PKG_BASE)

    def test_get_mockchain_command(self):
        builder = self.get_test_builder()

        builder.repos = [
            "http://example.com/rhel7",
            "http://example.com/fedora-20; rm -rf",
            "http://example.com/fedora-$releasever",
            "http://example.com/fedora-rawhide",
        ]
        builder.macros = {
            "foo": "bar",
            "foo; rm -rf": "bar",
            "foo2": "bar; rm -rf"
        }
        result_cmd = builder.gen_mockchain_command(self.BUILDER_PKG)
        expected = (
            "/usr/bin/mockchain -r fedora-20-i386 -l /tmp/copr-backend-test-tmp/build/"
            " -a http://example.com/rhel7 -a 'http://example.com/fedora-20; rm -rf' "
            "-a 'http://example.com/fedora-$releasever' -a http://example.com/fedora-rawhide "
            "-m '--define=foo bar' -m '--define=foo; rm -rf bar' -m '--define=foo2 bar; rm -rf'"
            " http://example.com/foovar-2.41.f21.src.rpm")
        assert result_cmd == expected

        builder.chroot = "fedora-rawhide"
        builder.repos = [
            "http://example.com/rhel7",
            "http://example.com/fedora-20; rm -rf",
            "http://example.com/fedora-$releasever",
            "http://example.com/fedora-rawhide",
        ]
        builder.macros = {
            "foo": "bar",
            "foo; rm -rf": "bar",
            "foo2": "bar; rm -rf"
        }
        result_cmd = builder.gen_mockchain_command(self.BUILDER_PKG)
        expected = (
            "/usr/bin/mockchain -r fedora-rawhide -l /tmp/copr-backend-test-tmp/build/"
            " -a http://example.com/rhel7 -a 'http://example.com/fedora-20; rm -rf' "
            "-a http://example.com/fedora-rawhide -a http://example.com/fedora-rawhide "
            "-m '--define=foo bar' -m '--define=foo; rm -rf bar' -m '--define=foo2 bar; rm -rf'"
            " http://example.com/foovar-2.41.f21.src.rpm")
        assert result_cmd == expected

    @mock.patch("backend.mockremote.builder.time")
    def test_run_command_and_wait_timeout(self, mc_time):
        build_cmd = "foo bar"
        builder = self.get_test_builder()

        mc_poller = mock.MagicMock()
        mc_poller.poll.return_value = {"contacted": {}, "dark": {}}
        builder.conn.run_async.return_value = None, mc_poller
        builder.timeout = 50

        mc_time.return_value = None

        with pytest.raises(BuilderTimeOutError):
            builder.run_command_and_wait(build_cmd)

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
        builder.run_command_and_wait(build_cmd)

    @mock.patch("backend.mockremote.builder.Popen")
    def test_download(self, mc_popen):
        builder = self.get_test_builder()

        for ret_code, expected_success in [(0, True), (1, False), (23, False)]:
            mc_cmd = mock.MagicMock()
            mc_cmd.communicate.return_value = self.STDOUT, self.STDERR
            mc_cmd.returncode = ret_code
            mc_popen.return_value = mc_cmd
            success, stdout, stderr = builder.download(self.BUILDER_PKG, self.BUILDER_REMOTE_BASEDIR)

            expected = (
                "/usr/bin/rsync -avH -e 'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
                " copr_builder@example.com:/tmp/copr-backend-test-tmp/build/results/fedora-20-i386/foovar-2.41.f21 "
                "'/tmp/copr-backend-test'/")

            assert mc_popen.call_args[0][0] == expected
            assert expected_success == success
            assert stdout == self.STDOUT
            assert stderr == self.STDERR

    def test_build(self):
        builder = self.get_test_builder()
        builder.modify_base_buildroot = MagicMock()
        builder.check_if_pkg_local_or_http = MagicMock()
        builder.check_if_pkg_local_or_http.return_value = self.BUILDER_PKG

        builder.get_package_version = MagicMock()
        builder.get_package_version.return_value = None

        builder.run_command_and_wait = MagicMock()
        successful_wait_result = {
            "contacted": {self.BUILDER_HOSTNAME: {
                "rc": 0, "stdout": self.STDOUT, "stderr": self.STDERR
            }},
            "dark": {}
        }
        builder.run_command_and_wait.return_value = successful_wait_result

        builder.check_build_success = MagicMock()
        builder.check_build_success.return_value = (self.STDERR, False, self.STDOUT)

        builder.collect_built_packages = MagicMock()

        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)
        assert success
        assert stdout == self.STDOUT
        assert stderr == self.STDERR
        assert builder.modify_base_buildroot.called
        assert builder.check_if_pkg_local_or_http.called
        assert builder.run_command_and_wait.called
        assert builder.check_build_success.called
        assert builder.collect_built_packages
        assert build_details == {}

        # test providing version
        builder.get_package_version.return_value = "srpm_version"
        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)

        assert "pkg_version" in build_details
        assert build_details["pkg_version"] == "srpm_version"

        # test timeout handle
        builder.run_command_and_wait.side_effect = BuilderTimeOutError("msg")
        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)
        assert not success
        assert stderr == "Timeout expired"
        assert build_details["pkg_version"] == "srpm_version"

        # remove timeout
        builder.run_command_and_wait.side_effect = None
        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)
        assert success

        # error inside wait result
        unsuccessful_wait_result = {
            "contacted": {self.BUILDER_HOSTNAME: {
                "rc": 1, "stdout": self.STDOUT, "stderr": self.STDERR
            }},
            "dark": {}
        }
        builder.run_command_and_wait.return_value = unsuccessful_wait_result
        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)
        assert not success

        # make wait result successful again
        builder.run_command_and_wait.return_value = successful_wait_result
        # error during build check
        builder.check_build_success.return_value = (self.STDERR, True, self.STDOUT)
        assert not success
        assert stdout == self.STDOUT
        assert stderr == self.STDERR

        # revert to successful check build
        builder.check_build_success.return_value = (self.STDERR, False, self.STDOUT)

        # check update build details
        def upd(bd, pkg):
            bd["foo"] = "bar"

        builder.collect_built_packages.side_effect = upd
        success, stdout, stderr, build_details = builder.build(self.BUILDER_PKG)
        assert success
        assert build_details["foo"] == "bar"
