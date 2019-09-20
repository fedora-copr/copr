# coding: utf-8
import os
import sys
import shutil
import tarfile
import tempfile
from munch import Munch

import pytest
from unittest import mock, skip
from unittest.mock import MagicMock

from run.copr_prune_results import Pruner
from run.copr_prune_results import main as prune_main

sys.path.append('../../run')

MODULE_REF = 'run.copr_prune_results'


@pytest.yield_fixture
def mc_runcmd():
    with mock.patch('{}.runcmd'.format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_bcr():
    with mock.patch('{}.BackendConfigReader'.format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_build_devel():
    with mock.patch('{}.uses_devel_repo'.format(MODULE_REF)) as handle:
        yield handle

@pytest.yield_fixture
def mc_pruner():
    with mock.patch('{}.Pruner'.format(MODULE_REF)) as handle:
        yield handle


class TestPruneResults(object):

    def setup_method(self, method):
        self.testresults = {
            'clime': {
                'example': [ 'epel-6-x86_64' ],
                'motionpaint': [ 'fedora-23-x86_64', 'fedora-24-x86_64' ],
            },
            '@copr': {
                'prunerepo': [ 'fedora-23-x86_64' ],
            },
        }

        self.tmp_dir = tempfile.mkdtemp()
        self.unpack_resource('testresults.tar.gz', self.tmp_dir)
        self.testresults_dir = os.path.join(self.tmp_dir, 'testresults')

        self.opts = Munch(
            prune_days=14,
            frontend_base_url = '<frontend_url>',
            destdir=self.testresults_dir
        )

    def teardown_method(self, method):
        shutil.rmtree(self.tmp_dir)

    ################################ helpers ################################

    def unpack_resource(self, resource_name, target):
        src_path = os.path.join(os.path.dirname(__file__), '..', '_resources', resource_name)
        with tarfile.open(src_path, 'r:gz') as tar_file:
            tar_file.extractall(target)

    ################################ tests ################################

    @skip("Fixme or remove, test doesn't work.")
    def test_run(self, mc_runcmd, mc_build_devel):
        mc_build_devel.return_value = False

        pruner = Pruner(self.opts)
        pruner.run()

        expected_call_count = 0
        for userdir in self.testresults:
            for projectdir in self.testresults[userdir]:
                for chrootdir in self.testresults[userdir][projectdir]:
                    prune_path = os.path.join(self.opts.destdir, userdir, projectdir, chrootdir)
                    mc_runcmd.assert_has_calls(
                        mock.call(
                            ['prunerepo', '--verbose', '--days={0}'.format(self.opts.prune_days), '--cleancopr', prune_path]
                        )
                    )
                    expected_call_count += 1
        assert mc_runcmd.call_count == expected_call_count

    @skip("Fixme or remove, test doesn't work.")
    def test_project_skipped_when_acr_disabled(self, mc_runcmd, mc_build_devel):
        mc_build_devel.return_value = True
        pruner = Pruner(self.opts)
        pruner.prune_project('<project_path>', '<username>', '<coprname>')

        assert not mc_runcmd.called

    @skip("Fixme or remove, test doesn't work.")
    def test_main(self, mc_pruner, mc_bcr):
        prune_main()

        assert mc_pruner.called
        assert mc_pruner.return_value.run.called
        assert mc_bcr.called
        assert mc_bcr.call_args[0][0] == '/etc/copr/copr-be.conf'

        os.environ['BACKEND_CONFIG'] = '<config_path>'
        prune_main()

        assert mc_bcr.call_args[0][0] == '<config_path>'
