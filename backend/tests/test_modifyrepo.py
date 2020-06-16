import contextlib
import os
import importlib
import logging
from unittest import mock
import pytest
import runpy
import shutil
import subprocess
import tempfile
import munch

from copr_backend.helpers import (
    BackendConfigReader,
    call_copr_repo,
    get_redis_connection,
)

from testlib.repodata import load_primary_xml
from testlib import (
    assert_files_in_dir,
    AsyncCreaterepoRequestFactory,
    minimal_be_config,
)

modifyrepo = 'run/copr-repo'

# pylint: disable=attribute-defined-outside-init

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
        with _lock() as opts:
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

    @staticmethod
    def _run_copr_repo(args):
        with mock.patch("sys.argv", ["copr-repo"] + args):
            filedict = runpy.run_path(modifyrepo)
            filedict["main"]()

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
        # TODO: the output should be empty
        # https://github.com/rpm-software-management/createrepo_c/issues/222
        # assert repoinfo['hrefs'] == set()
        assert repoinfo['hrefs'] == set([
            '00000001-prunerepo/prunerepo-1.1-1.fc23.noarch.rpm',
            '00000003-example/example-1.0.14-1.fc30.x86_64.rpm',
        ])

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
    def test_copr_repo_subdir_validator(self, add, capfd):
        assert 0 == call_copr_repo('/some/dir', add=add)
        # not using capsys because pytest/issues/5997
        _, err = capfd.readouterr()
        assert 'copr-repo: error: argument' in err

    @mock.patch("copr_backend.helpers.subprocess.call")
    def test_copr_repo_subdir_none_doesnt_raise(self, call):
        """ check that None is skipped in add (or delete) """
        call.return_value = 0 # exit status 0
        assert True == call_copr_repo('/some/dir', add=['xxx', None])
        assert len(call.call_args_list) == 1
        call = call.call_args_list[0]
        assert call[0][0] == ['copr-repo', '--batched', '/some/dir', '--add', 'xxx']
