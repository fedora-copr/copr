import mock
import unittest
from ..copr_rpmbuild.providers.pypi import PyPIProvider
from . import TestCase


class TestPyPIProvider(TestCase):
    def setUp(self):
        super(TestPyPIProvider, self).setUp()
        self.source_json = {"pypi_package_version": "1.52",
                            "pypi_package_name": "motionpaint",
                            "python_versions": [2, 3]}
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
       provider = PyPIProvider(self.source_json, self.resultdir, self.config)
       self.assertEqual(provider.pypi_package_version, "1.52")
       self.assertEqual(provider.pypi_package_name, "motionpaint")
       self.assertEqual(provider.python_versions, [2, 3])

    @mock.patch("rpmbuild.copr_rpmbuild.providers.pypi.run_cmd")
    @mock.patch("builtins.open")
    def test_produce_srpm(self, mock_open, run_cmd):
        provider = PyPIProvider(self.source_json, "/some/tmp/directory", self.config)
        provider.produce_srpm()
        assert_cmd = ["pyp2rpm", "motionpaint", "--srpm", "-d", "/some/tmp/directory",
                      "-b", "2", "-p", "3", "-v", "1.52"]
        run_cmd.assert_called_with(assert_cmd)
