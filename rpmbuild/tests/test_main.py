import os
import pytest
import unittest
import shutil

from main import produce_srpm
from copr_rpmbuild.helpers import SourceType

try:
     from unittest import mock
except ImportError:
     # Python 2 version depends on mock
     import mock


class TestTmpCleanup(unittest.TestCase):

    config = {}
    resultdir = "/path/to/non/existing/directory"
    task = {"source_type": SourceType.UPLOAD,
            "source_json": {"url": "http://foo.ex/somepackage.spec"}}

    @mock.patch("copr_rpmbuild.providers.spec.UrlProvider.produce_srpm")
    @mock.patch("main.shutil.rmtree", wraps=shutil.rmtree)
    def test_produce_srpm_cleanup(self, mock_rmtree, mock_produce_srpm):
        # Just to be sure, we are starting from zero
        assert mock_rmtree.call_count == 0

        # Test that we cleanup after successful build
        produce_srpm(self.task, self.config, self.resultdir)
        args, _ = mock_rmtree.call_args
        assert mock_rmtree.call_count == 1
        assert args[0].startswith("/tmp/copr-rpmbuild-")

        # Test that we cleanup after unsuccessful build
        mock_produce_srpm.side_effect = RuntimeError("Jeeez, something failed")
        with pytest.raises(RuntimeError):
            produce_srpm(self.task, self.config, self.resultdir)

        args, _ = mock_rmtree.call_args
        assert mock_rmtree.call_count == 2
        assert args[0].startswith("/tmp/copr-rpmbuild-")
