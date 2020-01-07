import os
import importlib
import logging
from unittest import mock
import pytest
import runpy
import shutil
import subprocess
import tempfile

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
