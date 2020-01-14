import os
import importlib
import logging
from unittest import mock
import pytest
import runpy
import shutil
import subprocess
import tempfile
from backend.helpers import call_copr_repo
from testlib.repodata import load_primary_xml

modifyrepo = 'run/copr-repo'


class TestModifyRepo(object):
    def setup_method(self, method):
        self.lockpath = tempfile.mkdtemp(prefix="copr-test-lockpath")
        self.os_env_patcher = mock.patch.dict(os.environ, {
            'PATH': os.environ['PATH']+':run',
            'COPR_TESTSUITE_LOCKPATH': self.lockpath,
        })
        self.os_env_patcher.start()

    def teardown_method(self, method):
        shutil.rmtree(self.lockpath)
        self.os_env_patcher.stop()

    def test_copr_modifyrepo_locks(self):
        filedict = runpy.run_path(modifyrepo)
        class XXX:
            pass
        opts = XXX()
        opts.log = logging.getLogger()
        opts.directory = 'non-existent'
        lock = filedict['lock']

        cmd = [modifyrepo, opts.directory, '--log-to-stdout']
        with lock(opts):
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

    @mock.patch.dict(os.environ, {'COPR_TESTSUITE_NO_OUTPUT': '1'})
    def test_copr_repo_add_subdir_devel(self, f_acr_on_and_first_build):
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
