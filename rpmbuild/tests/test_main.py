import os

import pytest

from copr_common.enums import BuildSourceEnum

from main import produce_srpm

from . import TestCase

try:
     from unittest import mock
except ImportError:
     # Python 2 version depends on mock
     import mock


class TestTmpCleanup(TestCase):

    config = {}
    workdir = None
    resultdir = None
    workspace = None

    task = {
        "chroot": None,
        "source_type": BuildSourceEnum.upload,
        "source_json": {"url": "http://foo.ex/somepackage.spec"},
        "project_owner": "u1",
        "project_name": "p1",
    }

    def auto_test_setup(self):
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    @mock.patch("copr_rpmbuild.providers.base.Provider.cleanup")
    @mock.patch("copr_rpmbuild.providers.spec.UrlProvider.produce_srpm")
    def test_produce_srpm_cleanup_no(self, mock_produce_srpm, _cleanup):
        # Test that we cleanup after successful build
        produce_srpm(self.task, self.config)
        # root + resultdir + workspace + not cleaned workdir
        directories = list(os.walk(self.workdir))
        assert len(directories) == 4

        mock_produce_srpm.side_effect = RuntimeError("Jeeez, something failed")
        with pytest.raises(RuntimeError):
            produce_srpm(self.task, self.config)

        # .. and plus one more workdir
        directories = list(os.walk(self.workdir))
        assert len(directories) == 5

    @mock.patch("copr_rpmbuild.providers.spec.UrlProvider.produce_srpm")
    def test_produce_srpm_cleanup_yes(self, mock_produce_srpm):
        # Test that we cleanup after successful build
        produce_srpm(self.task, self.config)

        # root + resultdir + workspace (cleaned workdir)
        directories = list(os.walk(self.workdir))
        assert len(directories) == 3

        mock_produce_srpm.side_effect = RuntimeError("Jeeez, something failed")
        with pytest.raises(RuntimeError):
            produce_srpm(self.task, self.config)

        # root + resultdir + workspace (cleaned workdir)
        directories = list(os.walk(self.workdir))
        assert len(directories) == 3
