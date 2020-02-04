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
        self.resultdir = "/path/to/resultdir"

    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    @mock.patch('copr_rpmbuild.providers.base.os.mkdir')
    def test_create_rpmmacros(self, mock_mkdir, mock_open):
        provider = Provider(self.source_json, self.resultdir, self.config)
        rpmmacros = mock.MagicMock()
        mock_open.return_value = rpmmacros
        provider.create_rpmmacros()
        mock_open.assert_called_with("{0}/.rpmmacros".format(provider.workdir), "w")
        calls = [
            mock.call.__enter__().write('%_disable_source_fetch 0\n'),
            mock.call.__enter__().write('%__urlhelper_localopts --proto -all,+https,+ftps\n'),
        ]
        rpmmacros.assert_has_calls(calls, any_order=True)
