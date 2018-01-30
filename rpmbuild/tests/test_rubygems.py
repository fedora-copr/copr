import mock
import unittest
from munch import Munch
from ..copr_rpmbuild.providers.rubygems import RubyGemsProvider
from . import TestCase


class TestRubyGemsProvider(TestCase):
    def setUp(self):
        super(TestRubyGemsProvider, self).setUp()
        self.source_json = {"gem_name": "A_123"}
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
        provider = RubyGemsProvider(self.source_json, self.resultdir, self.config)
        self.assertEqual(provider.gem_name, "A_123")

    @mock.patch("rpmbuild.copr_rpmbuild.providers.rubygems.run_cmd")
    @mock.patch("builtins.open")
    def test_produce_srpm(self, mock_open, run_cmd):
        provider = RubyGemsProvider(self.source_json, self.resultdir, self.config)
        provider.produce_srpm()
        assert_cmd = ["gem2rpm", "A_123", "--srpm", "-C", "/path/to/resultdir", "--fetch"]
        run_cmd.assert_called_with(assert_cmd)

    @mock.patch("rpmbuild.copr_rpmbuild.providers.rubygems.run_cmd")
    @mock.patch("builtins.open")
    def test_empty_license(self, mock_open, run_cmd):
        stderr = ("error: line 8: Empty tag: License:"
                  "Command failed: rpmbuild -bs --nodeps --define '_sourcedir /tmp/gem2rpm-foo-20170905-3367-c2flks'"
                  "--define '_srcrpmdir .' /tmp/gem2rpm-foo-20170905-3367-c2flks/rubygem-foo.spec")
        run_cmd.return_value = Munch({"stderr": stderr})
        provider = RubyGemsProvider(self.source_json, self.resultdir, self.config)
        with self.assertRaises(RuntimeError) as ex:
            provider.produce_srpm()
        self.assertIn("Not specifying a license means all rights are reserved", str(ex.exception))
