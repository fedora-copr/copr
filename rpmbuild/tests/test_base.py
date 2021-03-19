import os
from copr_rpmbuild.providers.base import Provider
from . import TestCase

try:
     from unittest import mock
     builtins = 'builtins'
except ImportError:
     # Python 2 version depends on mock
     import mock
     builtins = '__builtin__'

class TestProvider(TestCase):
    def setUp(self):
        super(TestProvider, self).setUp()
        self.source_json = {}

    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_create_rpmmacros(self, mock_mkdir, mock_open):
        provider = Provider(self.source_json, self.config)
        rpmmacros = mock.MagicMock()
        mock_open.return_value = rpmmacros
        provider.create_rpmmacros()
        mock_open.assert_called_with("{0}/.rpmmacros".format(provider.workdir), "w")
        calls = [
            mock.call.__enter__().write('%_disable_source_fetch 0\n'),
            mock.call.__enter__().write('%__urlhelper_localopts --proto -all,+https,+ftps\n'),
        ]
        rpmmacros.assert_has_calls(calls, any_order=True)

    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    @mock.patch('copr_rpmbuild.providers.base.Provider.create_rpmmacros')
    def test_workdir_in_workspace(self, _mock_create_rpmmacros, _mock_mkdir):
        ws = self.config.get("main", "workspace")
        provider = Provider(self.source_json, self.config)
        assert os.path.join(ws, "workdir-") in provider.workdir
