import pytest

from munch import Munch
from copr_rpmbuild.providers.rubygems import RubyGemsProvider
from . import TestCase

try:
     from unittest import mock
     builtins = 'builtins'
except ImportError:
     # Python 2 version depends on mock
     import mock
     builtins = '__builtin__'


class TestRubyGemsProvider(TestCase):
    def setUp(self):
        super(TestRubyGemsProvider, self).setUp()
        self.source_json = {"gem_name": "A_123"}

    @mock.patch("{0}.open".format(builtins))
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_init(self, mock_mkdir, mock_open):
        provider = RubyGemsProvider(self.source_json, self.config)
        self.assertEqual(provider.gem_name, "A_123")

    @mock.patch("copr_rpmbuild.providers.rubygems.run_cmd")
    @mock.patch("{0}.open".format(builtins))
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_produce_srpm(self, mock_mkdir, mock_open, run_cmd):
        provider = RubyGemsProvider(self.source_json, self.config)
        provider.produce_srpm()
        assert_cmd = ["gem2rpm", "A_123", "--srpm",
                      "-C", self.config.get("main", "resultdir"), "--fetch"]
        run_cmd.assert_called_with(assert_cmd)

    @mock.patch("copr_rpmbuild.providers.rubygems.run_cmd")
    @mock.patch("{0}.open".format(builtins))
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_empty_license(self, mock_mkdir, mock_open, run_cmd):
        stderr = ("error: line 8: Empty tag: License:"
                  "Command failed: rpmbuild -bs --nodeps --define '_sourcedir /tmp/gem2rpm-foo-20170905-3367-c2flks'"
                  "--define '_srcrpmdir .' /tmp/gem2rpm-foo-20170905-3367-c2flks/rubygem-foo.spec")
        run_cmd.return_value = Munch({"stderr": stderr})
        provider = RubyGemsProvider(self.source_json, self.config)
        with pytest.raises(RuntimeError) as ex:
            provider.produce_srpm()
            assert "Not specifying a license means all rights are reserved" in str(ex.exception)
