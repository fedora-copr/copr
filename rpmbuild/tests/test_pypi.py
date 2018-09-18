from copr_rpmbuild.providers.pypi import PyPIProvider
from . import TestCase

try:
     from unittest import mock
     builtins = 'builtins'
except ImportError:
     # Python 2 version depends on mock
     import mock
     builtins = '__builtin__'


class TestPyPIProvider(TestCase):
    def setUp(self):
        super(TestPyPIProvider, self).setUp()
        self.source_json = {"pypi_package_version": "1.52",
                            "pypi_package_name": "motionpaint",
                            "spec_template": "epel7",
                            "python_versions": [2, 3]}
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
       provider = PyPIProvider(self.source_json, self.resultdir, self.config)
       self.assertEqual(provider.pypi_package_version, "1.52")
       self.assertEqual(provider.pypi_package_name, "motionpaint")
       self.assertEqual(provider.spec_template, "epel7")
       self.assertEqual(provider.python_versions, [2, 3])

    @mock.patch("copr_rpmbuild.providers.pypi.run_cmd")
    @mock.patch("{0}.open".format(builtins))
    def test_produce_srpm(self, mock_open, run_cmd):
        provider = PyPIProvider(self.source_json, "/some/tmp/directory", self.config)
        provider.produce_srpm()
        assert_cmd = ["pyp2rpm", "motionpaint", "-t", "epel7", "--srpm", "-d", "/some/tmp/directory",
                      "-b", "2", "-p", "3", "-v", "1.52"]
        run_cmd.assert_called_with(assert_cmd)
