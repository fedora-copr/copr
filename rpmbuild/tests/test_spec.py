import mock
import unittest
import configparser
from ..copr_rpmbuild.providers.spec import SpecUrlProvider
from . import TestCase


class TestSpecUrlProvider(TestCase):
    def setUp(self):
        super(TestSpecUrlProvider, self).setUp()
        self.source_json = {"url": u"http://foo.ex/somepackage.spec"}
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
        provider = SpecUrlProvider(self.source_json, self.resultdir, self.config)
        self.assertEqual(provider.url, "http://foo.ex/somepackage.spec")

    @mock.patch('requests.get')
    @mock.patch("rpmbuild.copr_rpmbuild.providers.spec.run_cmd")
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_produce_srpm(self, mock_open, run_cmd, mock_get):
        provider = SpecUrlProvider(self.source_json, self.resultdir, self.config)
        provider.produce_srpm()
        run_cmd.assert_called_with(["rpkg", "srpm", "--outdir", self.resultdir,
                                    "--spec", '{}/somepackage.spec'.format(provider.workdir)],
                                   cwd=provider.workdir)

    @mock.patch('requests.get')
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_save_spec(self, mock_open, mock_get):
        provider = SpecUrlProvider(self.source_json, self.resultdir, self.config)
        provider.save_spec()
        mock_open.assert_called_with("{}/somepackage.spec".format(provider.workdir), "w")
