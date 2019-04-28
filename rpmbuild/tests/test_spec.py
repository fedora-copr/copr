import configparser

import os
import distro
import pytest
import tempfile

try:
    from httmock import urlmatch, HTTMock

    @urlmatch(netloc=r'(.*\.)?example\.com$')
    def example_com_match(url, request):
        return 'some-content'

except:
    pass


from copr_rpmbuild.providers.spec import UrlProvider
from . import TestCase

try:
     from unittest import mock
     builtins = 'builtins'
except ImportError:
     # Python 2 version depends on mock
     import mock
     builtins = '__builtin__'


class TestUrlProvider(TestCase):
    def test_setup(self):
        self.source_json = {"url": u"http://foo.ex/somepackage.spec"}
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
        provider = UrlProvider(self.source_json, self.resultdir, self.config)
        self.assertEqual(provider.url, "http://foo.ex/somepackage.spec")

    @mock.patch('requests.get')
    @mock.patch("copr_rpmbuild.providers.spec.run_cmd")
    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    def test_produce_srpm(self, mock_open, run_cmd, mock_get):
        provider = UrlProvider(self.source_json, self.resultdir, self.config)
        provider.produce_srpm()
        run_cmd.assert_called_with(["rpkg", "srpm", "--outdir", self.resultdir,
                                    "--spec", '{0}/somepackage.spec'.format(provider.workdir)],
                                   cwd=provider.workdir)

    @mock.patch('requests.get')
    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    def test_save_spec(self, mock_open, mock_get):
        provider = UrlProvider(self.source_json, self.resultdir, self.config)
        provider.save_spec()
        mock_open.assert_called_with("{0}/somepackage.spec".format(provider.workdir), "w")


class TestUrlProviderQueryString(TestCase):
    def test_setup(self):
        self.json_1 = {
            'url': "http://example.com/"
                   "srelay-0.4.8p3-0.20181224.git688764b.fc10.3sunshine.src.rpm?dl=1",
        }
        self.json_2 = { 'url': "http://example.com/test.spec?a=1&b=2" }
        self.resultdir = tempfile.mkdtemp()

    @pytest.mark.skipif(distro.id() in ['rhel', 'centos'] and
                            distro.major_version() == '6',
                        reason='on httmock on rhel6')
    def test_srpm_query_string(self):
        with HTTMock(example_com_match):
            provider = UrlProvider(self.json_1, self.resultdir, self.config)
            provider.produce_srpm()
            file = os.path.join(
                    self.resultdir,
                    "srelay-0.4.8p3-0.20181224.git688764b.fc10.3sunshine.src.rpm",
            )
            with open(file, 'r') as f:
                assert f.read() == 'some-content'

    @pytest.mark.skipif(distro.id() in ['rhel', 'centos'] and
                            distro.major_version() == '6',
                        reason='on httmock on rhel6')
    def test_spec_query_string(self):
        with HTTMock(example_com_match):
            provider = UrlProvider(self.json_2, self.resultdir, self.config)
            filename = provider.save_spec()
            with open(filename, 'r') as f:
                assert f.read() == 'some-content'
            assert filename.endswith('.spec')
