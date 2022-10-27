"""
Testing for 'copr-repo' script (Copr Backend codebase)
"""

import contextlib
import glob
import logging
import os
import runpy
import shutil
import subprocess
import tempfile
import time
from unittest import mock

import distro
import munch
from packaging import version
import pytest

from testlib.repodata import load_primary_xml
from testlib import (
    assert_files_in_dir,
    AsyncCreaterepoRequestFactory,
    minimal_be_config,
)

from copr_prune_results import run_prunerepo

from copr_common.redis_helpers import get_redis_connection
from copr_backend.helpers import (
    BackendConfigReader,
    call_copr_repo,
)


modifyrepo = 'run/copr-repo'
fix_gpg_script = 'run/copr_fix_gpg.py'

# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-public-methods

@contextlib.contextmanager
def _lock(directory="non-existent"):
    filedict = runpy.run_path(modifyrepo)
    opts = munch.Munch()
    opts.log = logging.getLogger()
    opts.directory = directory
    lock = filedict['lock']
    with lock(opts):
        yield opts

class TestModifyRepo(object):
    def setup_method(self, method):
        self.workdir = tempfile.mkdtemp(prefix="copr-test-copr-repo")
        self.be_config = minimal_be_config(self.workdir)
        self.os_env_patcher = mock.patch.dict(os.environ, {
            'PATH': os.environ['PATH']+':run',
            'COPR_TESTSUITE_LOCKPATH': self.workdir,
            'COPR_BE_CONFIG': self.be_config,
        })
        self.os_env_patcher.start()
        self.redis = get_redis_connection(
            BackendConfigReader(self.be_config).read())
        self.request_createrepo = AsyncCreaterepoRequestFactory(self.redis)

    def teardown_method(self, method):
        shutil.rmtree(self.workdir)
        self.os_env_patcher.stop()
        self.redis.flushdb()

    def test_copr_modifyrepo_locks(self):
        with _lock(self.workdir) as opts:
            cmd = [modifyrepo, opts.directory, '--log-to-stdout']
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            try:
                proc.communicate(timeout=2)
                assert 0 # this shouldn't happen
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
                assert b"acquired lock" not in out
                assert b"acquired lock" not in err

        # with released lock
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        out, err = proc.communicate(timeout=5)
        proc.kill()
        assert b"acquired lock" in err

    @mock.patch.dict(os.environ, {'COPR_TESTSUITE_NO_OUTPUT': '1'})
    def test_copr_repo_add_subdir(self, f_second_build):
        _unused = self
        ctx = f_second_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')
        empty_repodata = load_primary_xml(repodata)

        assert empty_repodata['names'] == set()
        assert call_copr_repo(chrootdir, add=[ctx.builds[0]])
        first_repodata = load_primary_xml(repodata)

        assert first_repodata['hrefs'] == {'00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm'}
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])
        second_repodata = load_primary_xml(repodata)
        assert second_repodata['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm'
        }
        assert_files_in_dir(chrootdir,
                            ["00000002-example", "00000001-prunerepo"], [])

    def test_copr_repo_batched_createrepo(self, f_second_build):
        ctx = f_second_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')
        assert call_copr_repo(chrootdir, add=[ctx.builds[0]])
        first_repodata = load_primary_xml(repodata)
        assert first_repodata['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
        }
        # call copr-repo for second build while separate request for removal of
        # the first repo was requested
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": ["00000001-prunerepo"],
        })
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])

        second_repodata = load_primary_xml(repodata)
        assert second_repodata['hrefs'] == {
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm'
        }
        assert_files_in_dir(chrootdir, ["00000002-example"],
                            ["00000001-prunerepo"])

    def test_copr_repo_batched_already_processed(self, f_second_build):
        ctx = f_second_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()
        with _lock(chrootdir) as opts:
            # delay processing by lock
            cmd = [modifyrepo, "--batched", "--log-to-stdout",
                   opts.directory, "--add", ctx.builds[1]]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            try:
                # start the process
                proc.communicate(timeout=2)
                assert 0 # this shouldn't happen
            except subprocess.TimeoutExpired:
                pass
            while True:
                keys = self.redis.keys("createrepo_batched*")
                if len(keys) == 1:
                    break
            key = keys[0]
            # claim we did it!
            self.redis.hset(key, "status", "success")

        (out, err) = proc.communicate()
        assert out == b""
        err_decoded = err.decode("utf-8")
        assert "Task processed by other process" in err_decoded
        assert proc.returncode == 0
        # nothing changed, copr-repo went no-op because it thinks we already
        # processed it
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()
        assert_files_in_dir(chrootdir,
                            ["00000001-prunerepo", "00000002-example"], [])

    def test_copr_repo_batched_two_builds(self, f_third_build):
        """ Two finished builds requesting createrepo at the same time """
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm'
        }
        # other process requested adding build[0]
        self.request_createrepo.get(chrootdir, {
            "add": [ctx.builds[0]],
            "delete": [],
        })
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm'
        }

        # build 3 stays undeleted
        assert_files_in_dir(chrootdir,
                            ["00000001-prunerepo", "00000002-example",
                             "00000003-example"], [])

    def test_copr_repo_batched_full(self, f_third_build):
        """
        Full createrepo which also does one removal and one addition
        for others.
        """
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')

        # createrepo was not run for the packages, yet
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()

        # one other process requested removal, another addition
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": [ctx.builds[1]],
        })
        self.request_createrepo.get(chrootdir, {
            "add": [ctx.builds[0]],
            "delete": [],
        })

        # merged full createrepo run, still does the removal
        assert call_copr_repo(chrootdir)

        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
            '00000003-example/example-1.0.14-1.fc30.x86_64.rpm',
        }
        assert_files_in_dir(chrootdir,
                            ["00000001-prunerepo", "00000003-example"],
                            ["00000002-example"])

    def test_copr_repo_batched_others_full(self, f_third_build):
        """
        We add one build, but other request is to
        - remove one build
        - run full createrepo
        """
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')

        # check no one run craterepo against the builds
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()

        # one build finished (the second one)
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm'
        }

        # other process requested full run
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": [],
            "full": True,
        })

        # other requested removal of first build
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": [ctx.builds[0]],
            "full": True,
        })

        # we request addition of third build
        assert call_copr_repo(chrootdir, add=[ctx.builds[2]])
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000002-example/example-1.0.4-1.fc23.x86_64.rpm',
            '00000003-example/example-1.0.14-1.fc30.x86_64.rpm',
        }
        assert_files_in_dir(chrootdir,
                            ["00000002-example", "00000003-example"],
                            ["00000001-prunerepo"])

    def test_copr_repo_add_del_mixup(self, f_third_build):
        """
        Check that if one process requests adding one build, and another
        removal, we still remove it.
        """
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')

        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == set()

        # delete request
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": [ctx.builds[1]],
        })

        # and add request for the same build
        assert call_copr_repo(chrootdir, add=[ctx.builds[1]])

        repoinfo = load_primary_xml(repodata)
        output = subprocess.check_output(["createrepo_c", "--version"],
                                         universal_newlines=True)
        expected_hrefs = set()
        if version.parse(output.split()[1]) < version.parse("0.16.1"):
            # https://github.com/rpm-software-management/createrepo_c/issues/222
            expected_hrefs = set([
                '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
                '00000003-example/example-1.0.14-1.fc30.x86_64.rpm',
            ])
        assert repoinfo['hrefs'] == expected_hrefs


    @mock.patch.dict(os.environ, {'COPR_TESTSUITE_NO_OUTPUT': '1'})
    def test_copr_repo_add_subdir_devel(self, f_acr_on_and_first_build):
        _unused = self
        ctx = f_acr_on_and_first_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')
        devel_repodata = os.path.join(chrootdir, 'devel', 'repodata')
        empty_repodata = load_primary_xml(repodata)
        assert empty_repodata == load_primary_xml(devel_repodata)
        assert call_copr_repo(chrootdir, add=[ctx.builds[0]], devel=True)

        # shouldn't change
        assert empty_repodata == load_primary_xml(repodata)
        updated = load_primary_xml(devel_repodata)
        assert updated['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
        }

        # the --devel repdata need to have 'xml:base' element, otherwise those
        # wouldn't be able to reference ../ locations
        assert updated['packages']['prunerepo']['xml:base'] == \
                'https://example.com/results/john/empty/fedora-rawhide-x86_64'

    @pytest.mark.parametrize('add', [
        ["aaa", ''],
        ["File 1"],
        ["slash/in/path"],
        [".."],
    ])
    def test_copr_repo_subdir_validator(self, add, caplog):
        log = logging.getLogger()
        assert call_copr_repo('/some/dir', add=add, logger=log) == 0
        # not using capsys because pytest/issues/5997
        messages = [r.message for r in caplog.records]
        assert any(['copr-repo: error: argument' in m for m in messages])

    @mock.patch("copr_backend.helpers.subprocess.Popen")
    def test_copr_repo_subdir_none_doesnt_raise(self, popen):
        """ check that None is skipped in add (or delete) """
        popen.return_value.communicate.return_value = ("", "")
        popen.return_value.returncode = 0
        assert True == call_copr_repo('/some/dir', add=['xxx', None])
        assert len(popen.call_args_list) == 1
        call = popen.call_args_list[0]
        assert call[0][0] == ['copr-repo', '--batched', '/some/dir', '--add', 'xxx']

    @staticmethod
    @mock.patch("copr_backend.helpers.subprocess.Popen")
    def test_copr_repo_do_stat(popen):
        """ do_stat=True adds --do-stat option """
        popen.return_value.communicate.return_value = ("", "")
        popen.return_value.returncode = 0
        assert call_copr_repo("/some/dir", do_stat=True) is True
        assert len(popen.call_args_list) == 1
        call = popen.call_args_list[0]
        assert call[0][0] == ["copr-repo", "--batched", "/some/dir", "--do-stat"]

    @pytest.mark.parametrize('do_stat', [True, False])
    @mock.patch("copr_backend.helpers.subprocess.Popen")
    def test_copr_repo_run_createrepo(self, popen, do_stat):
        """ Check that we run createrepo_c with appropriate arguments """

        # Mock the run_prunerepo properly
        popen.return_value.communicate.return_value = ("","")
        popen.return_value.returncode = 0
        repodir = os.path.join(self.workdir, "testrepo")
        repodata = os.path.join(repodir, "repodata")
        xml = os.path.join(repodata, "repomd.xml")
        os.makedirs(repodata)
        with open(xml, 'w'):
            pass
        filedict = runpy.run_path(modifyrepo)
        opts = munch.Munch()
        opts.directory = repodir
        opts.add = []
        opts.delete = []
        opts.full = True
        opts.devel = False
        opts.do_stat = do_stat
        opts.log = logging.getLogger()
        opts.rpms_to_remove = []

        # run the method
        filedict["run_createrepo"](opts)

        additional_args = [] if do_stat else ["--skip-stat"]

        assert popen.call_args_list[0][0][0] == \
            ["/usr/bin/createrepo_c", repodir, "--database",
             "--ignore-lock", "--local-sqlite", "--cachedir", "/tmp/",
             "--workers", "8", "--update"] + additional_args

    @pytest.mark.skipif(
        distro.id() == 'fedora' and int(distro.version()) >= 36,
        reason="createrepo_c dropped md5 checksum support"
    )
    def test_copr_repo_el5(self, f_third_build):
        """
        Test that special createrepo_c arguments are used when creating
        el5 repositories.
        """
        _unused = self
        ctx = f_third_build
        chroot = ctx.chroots[0]
        old_chrootdir = os.path.join(ctx.empty_dir, chroot)
        # assure that it looks like el5 directory
        chrootdir = os.path.join(ctx.empty_dir, "rhel-5-x86_64")
        repodata = os.path.join(chrootdir, 'repodata')
        subprocess.check_call(["cp", "-r", old_chrootdir, chrootdir])
        assert call_copr_repo(old_chrootdir, add=[ctx.builds[0]],
                              delete=[ctx.builds[2]])
        assert call_copr_repo(chrootdir, add=[ctx.builds[0]],
                              delete=[ctx.builds[2]])
        repoinfo = load_primary_xml(repodata)
        assert repoinfo['hrefs'] == {
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
        }

        # rhel-5 contains md5 checksums
        assert_files_in_dir(chrootdir,
                            ["00000002-example", "00000001-prunerepo"],
                            ["00000003-example"])
        assert repoinfo["packages"]["prunerepo"]["chksum_type"] == "md5"

        # other chroots are sha256
        repodata = os.path.join(old_chrootdir, 'repodata')
        repoinfo = load_primary_xml(repodata)
        assert repoinfo["packages"]["prunerepo"]["chksum_type"] == "sha256"

    def test_copr_repo_noop(self, f_second_build):
        """
        When anyone requests removal (or addition) of directories which do not
        exist, there's no point in running the createrepo_c at all.
        """
        ctx = f_second_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        self.request_createrepo.get(chrootdir, {
            "add": [],
            "delete": ["non-existing-dir"],
        })
        assert call_copr_repo(chrootdir, add=["non-existing-dir-2"])
        repodata = os.path.join(chrootdir, 'repodata')
        repoinfo = load_primary_xml(repodata)
        assert repoinfo["hrefs"] == set()
        keys = self.redis.keys("createrepo_batch*")
        assert len(keys) == 1
        task_dict = self.redis.hgetall(keys[0])
        assert task_dict["status"] == "success"

    @staticmethod
    @mock.patch("copr_backend.helpers.subprocess.Popen")
    def test_copr_repo_rpms_to_remove_in_call(popen):
        """ check that list of rpm files to be removed is added to copr-repo call """
        popen.return_value.communicate.return_value = ("","")
        popen.return_value.returncode = 0

        assert call_copr_repo('/some/dir', rpms_to_remove=['xxx.rpm'])
        assert len(popen.call_args_list) == 1
        call = popen.call_args_list[0]
        assert call[0][0] == ['copr-repo', '--batched', '/some/dir', '--rpms-to-remove', 'xxx.rpm']

    def test_copr_repo_rpms_to_remove_passes(self, f_third_build):
        _unused = self
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)

        assert_files_in_dir(chrootdir, ["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"], [])
        assert call_copr_repo(chrootdir, rpms_to_remove=["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"])
        assert_files_in_dir(chrootdir, [], ["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"])

    def test_copr_repo_rpms_to_remove_passes_2(self, f_third_build):
        _unused = self
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)

        assert_files_in_dir(chrootdir, ["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"], [])
        assert call_copr_repo(chrootdir, rpms_to_remove=[])
        assert_files_in_dir(chrootdir, ["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"], [])

    def test_copr_repo_rpms_to_remove_passes_3(self, f_third_build):
        _unused = self
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)

        assert call_copr_repo(chrootdir, add=[ctx.builds[0]])
        assert_files_in_dir(chrootdir, ["00000001-prunerepo", "00000002-example"], [])
        assert call_copr_repo(chrootdir,
                              rpms_to_remove=["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"])
        assert_files_in_dir(chrootdir,
                            [],
                            ["00000002-example/example-1.0.4-1.fc23.x86_64.rpm"])
        assert_files_in_dir(chrootdir,
                            ["00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm"],
                            [])

    def test_comps_present(self, f_third_build):
        _unused = self
        ctx = f_third_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        copms_path = os.path.join(chrootdir, "comps.xml")
        with open(copms_path, "w"):
            pass

        assert call_copr_repo(chrootdir)
        name = glob.glob(os.path.join(chrootdir, "repodata", "*-comps.xml.gz"))
        assert os.path.exists(name[0])


    @mock.patch("copr_prune_results.LOG", logging.getLogger())
    def test_run_prunerepo(self, f_builds_to_prune):
        _unused = self
        ctx = f_builds_to_prune
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        assert_files_in_dir(os.path.join(chrootdir, '00999999-dummy-pkg'),
                            ["dummy-pkg-1-1.fc34.x86_64.rpm"],
                            [])
        run_prunerepo(chrootdir, 'john', 'empty', chroot, 0)
        assert_files_in_dir(os.path.join(chrootdir, '00999999-dummy-pkg'),
                            ["prune.log"],
                            ["dummy-pkg-1-1.fc34.x86_64.rpm"])
        logfile = os.path.join(chrootdir, "00999999-dummy-pkg", "prune.log")
        with open(logfile, "r") as fd:
            lines = fd.readlines()
            assert len(lines) == 1
            assert "pruned on" in lines[0]

    @pytest.mark.parametrize('run_bg', [True, False])
    @mock.patch.dict(os.environ, {'COPR_TESTSUITE_NO_OUTPUT': '1'})
    def test_copr_repo_timeouted_check(self, f_second_build, run_bg):
        _unused = self
        ctx = f_second_build
        chroot = ctx.chroots[0]
        chrootdir = os.path.join(ctx.empty_dir, chroot)
        repodata = os.path.join(chrootdir, 'repodata')

        # empty repodata at the beginning
        empty_repodata = load_primary_xml(repodata)
        assert empty_repodata['names'] == set()

        pid = os.fork()
        if not pid:
            # give parent some time to lock the repo
            time.sleep(1)
            # Run the blocked (by parent) createrepo, it must finish soon
            # anway because parent will claim the task is done.
            assert call_copr_repo(chrootdir, add=[ctx.builds[1]])
            # sys.exit() can not be used in testsuite
            os._exit(0)  # pylint: disable=protected-access

        with _lock(chrootdir):
            # give the child some time to fill its Redis keys
            sleeper = 1
            while True:
                if len(self.redis.keys()) > 0:
                    break
                sleeper += 1
                time.sleep(0.1)
                assert sleeper < 10*15  # 15s

            assert len(self.redis.keys()) == 1
            key = self.redis.keys()[0]

            # Claim we did that task (even if not) and check that the child
            # finishes after some time.
            if not run_bg:
                self.redis.hset(key, "status", "success")
                assert os.wait()[1] == 0
                assert self.redis.get(key) is None

        if run_bg:
            # actually process the background job!
            assert os.wait()[1] == 0

        repodata = load_primary_xml(repodata)
        if run_bg:
            assert repodata['names'] == {'example'}
        else:
            assert repodata['names'] == set()


@mock.patch("copr_backend.helpers.subprocess.Popen")
def test_aws_cdn_refresh(popen):
    """ Check that we run createrepo_c with appropriate arguments """

    # Mock the run_prunerepo properly
    popen.return_value.communicate.return_value = ("","")
    popen.return_value.returncode = 0
    method = runpy.run_path(fix_gpg_script)["invalidate_aws_cloudfront_data"]

    opts = munch.Munch()
    opts.results_baseurl = "https://example.com/results"
    opts.aws_cloudfront_distribution = "XYZ"
    method(opts, "jdoe", "foo", "fedora-rawhide-x86_64")

    assert popen.call_args_list[0][0][0] == \
        ["aws", "cloudfront", "create-invalidation", "--distribution-id", "XYZ",
         "--paths", "/results/jdoe/foo/fedora-rawhide-x86_64/*"]
