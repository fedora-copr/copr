import configparser

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
    def setUp(self):
        super(TestUrlProvider, self).setUp()
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
