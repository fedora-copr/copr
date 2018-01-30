import mock
from mock import MagicMock
from mock import call

from ..copr_rpmbuild.providers.base import Provider
from . import TestCase


class TestProvider(TestCase):
    def setUp(self):
        super(TestProvider, self).setUp()
        self.source_json = {}
        self.resultdir = "/path/to/resultdir"

    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_create_rpmmacros(self, mock_open):
        provider = Provider(self.source_json, self.resultdir, self.config)
        rpmmacros = MagicMock()
        mock_open.return_value = rpmmacros
        provider.create_rpmmacros()
        mock_open.assert_called_with("{}/.rpmmacros".format(provider.workdir), "w")
        calls = [
            call.__enter__().write('%_disable_source_fetch 0\n'),
            call.__enter__().write('%__urlhelper_localopts --proto -all,+https,+ftps\n'),
        ]
        rpmmacros.assert_has_calls(calls, any_order=True)

