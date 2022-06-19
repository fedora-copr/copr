import configparser

import os
import distro
import pytest

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
    def auto_test_setup(self):
        self.source_json = {"url": u"http://foo.ex/somepackage.spec"}

    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_init(self, mock_mkdir, mock_open):
        provider = UrlProvider(self.source_json, self.config)
        self.assertEqual(provider.url, "http://foo.ex/somepackage.spec")

    @mock.patch('copr_common.request.SafeRequest.get')
    @mock.patch("copr_rpmbuild.providers.base.run_cmd")
    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    @mock.patch("copr_rpmbuild.providers.spec.UrlProvider.create_rpmmacros")
    @mock.patch("copr_rpmbuild.providers.spec.UrlProvider.generate_mock_config")
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_produce_srpm(self, mock_mkdir, mock_generate_mock_config,
                          _mock_create_rpmmacros, mock_open, run_cmd, mock_get):
        mock_generate_mock_config.return_value = "/path/to/mock-source-build.cfg"
        macros = {"_disable_source_fetch": 0}
        provider = UrlProvider(self.source_json, self.config, macros)
        provider.produce_srpm()
        args = [
            'mock', '-r', '/path/to/mock-source-build.cfg',
            '--buildsrpm',
            '--spec', '{0}/somepackage.spec'.format(provider.workdir),
            '--resultdir', self.config.get("main", "resultdir"),
            '--define', '_disable_source_fetch 0',
        ]
        run_cmd.assert_called_with(args, cwd=provider.workdir)

    @mock.patch('copr_common.request.SafeRequest.get')
    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_save_spec(self, mock_mkdir, mock_open, mock_get):
        provider = UrlProvider(self.source_json, self.config)
        provider.save_spec()
        mock_open.assert_called_with("{0}/somepackage.spec".format(provider.workdir), "w")


class TestUrlProviderQueryString(TestCase):
    def auto_test_setup(self):
        self.json_1 = {
            'url': "http://example.com/"
                   "srelay-0.4.8p3-0.20181224.git688764b.fc10.3sunshine.src.rpm?dl=1",
        }
        self.json_2 = { 'url': "http://example.com/test.spec?a=1&b=2" }
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    @pytest.mark.skipif(distro.id() in ['rhel', 'centos'] and
                            distro.major_version() == '6',
                        reason='on httmock on rhel6')
    def test_srpm_query_string(self):
        with HTTMock(example_com_match):
            provider = UrlProvider(self.json_1, self.config)
            provider.produce_srpm()
            file = os.path.join(
                    self.config.get("main", "resultdir"),
                    "srelay-0.4.8p3-0.20181224.git688764b.fc10.3sunshine.src.rpm",
            )
            with open(file, 'r') as f:
                assert f.read() == 'some-content'

    @pytest.mark.skipif(distro.id() in ['rhel', 'centos'] and
                            distro.major_version() == '6',
                        reason='on httmock on rhel6')
    def test_spec_query_string(self):
        with HTTMock(example_com_match):
            provider = UrlProvider(self.json_2, self.config)
            filename = provider.save_spec()
            with open(filename, 'r') as f:
                assert f.read() == 'some-content'
            assert filename.endswith('.spec')
