import os
import pytest
import unittest
import shutil

from main import produce_srpm
from copr_rpmbuild.helpers import SourceType

try:
     from unittest import mock
     EPEL = False
except ImportError:
     # Python 2 version depends on mock
     import mock
     EPEL = True


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
        assert mock_rmtree.call_count == (1 if not EPEL else 2)
        for call in mock_rmtree.call_args_list:
            args, _ = call
            assert args[0].startswith("/tmp/copr-rpmbuild-")

        # Just to check, that on EPEL it recursively removes one directory, 
        # not two different directories. Do not run this check on Fedora/Python3
        # because there the directory is removed on one rmtree call.
        if EPEL:
            assert mock_rmtree.call_args_list[1][0][0] == \
                os.path.join(mock_rmtree.call_args_list[0][0][0], "obtain-sources")

        # Test that we cleanup after unsuccessful build
        mock_produce_srpm.side_effect = RuntimeError("Jeeez, something failed")
        with pytest.raises(RuntimeError):
            produce_srpm(self.task, self.config, self.resultdir)

        assert mock_rmtree.call_count == (2 if not EPEL else 4)
        for call in mock_rmtree.call_args_list:
            args, _ = call
            assert args[0].startswith("/tmp/copr-rpmbuild-")
