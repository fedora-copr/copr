import mock
import unittest
from ..copr_rpmbuild.providers.spec import SpecUrlProvider


class TestSpecUrlProvider(unittest.TestCase):
    def setUp(self):
        self.source_json = {"url": "http://foo.ex/somepackage.spec"}

    def test_init(self):
        provider = SpecUrlProvider(self.source_json)
        self.assertEqual(provider.url, "http://foo.ex/somepackage.spec")

    @mock.patch("rpmbuild.copr_rpmbuild.providers.spec.run_cmd")
    def test_produce_srpm(self, run_cmd):
        provider = SpecUrlProvider(self.source_json, workdir="/some/tmp/directory")
        provider.produce_srpm()
        run_cmd.assert_called_with(["rpkg", "srpm"], cwd="/some/tmp/directory")

    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_create_rpmmacros(self, mock_open):
        provider = SpecUrlProvider(self.source_json, workdir="/some/tmp/directory")
        provider.create_rpmmacros()
        mock_open.assert_called_with("/some/tmp/directory/.rpmmacros", "w")
        # @TODO test the .rpmmacros contents

    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_touch_sources(self, mock_open):
        provider = SpecUrlProvider(self.source_json, workdir="/some/tmp/directory")
        provider.touch_sources()
        mock_open.assert_called_with("/some/tmp/directory/sources", "w")

    @mock.patch('requests.get')
    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_create_rpmmacros(self, mock_open, mock_get):
        provider = SpecUrlProvider(self.source_json, workdir="/some/tmp/directory")
        provider.save_spec()
        mock_open.assert_called_with("/some/tmp/directory/somepackage.spec", "w")
