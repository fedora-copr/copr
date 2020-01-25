import os
import mock
import pytest
import tempfile
import shutil
from json import loads
from copr.v3 import ModuleProxy


class TestModuleProxy(object):
    config_auth = {
        "copr_url": "http://copr",
        "login": "test_api_login",
        "token": "test_api_token",
    }

    def setup_method(self, method):
        self.tmpdir = tempfile.mkdtemp(prefix='test-python-copr-modules')
        self.yaml_file = os.path.join(self.tmpdir, 'test.yaml')
        with open(self.yaml_file, 'w') as f:
            f.write("")

    def teardown_method(self, method):
        shutil.rmtree(self.tmpdir)

    @pytest.mark.parametrize('distgit_opt', [None, 'fedora'])
    @mock.patch('copr.v3.requests.requests.request')
    def test_module_dist_git_choice_url(self, request, distgit_opt):
        proxy = ModuleProxy(self.config_auth)
        proxy.build_from_url('owner', 'project', 'http://test.yaml',
                             distgit=distgit_opt)

        assert len(request.call_args_list) == 1
        call = request.call_args_list[0]
        kwargs = call[1]
        json = kwargs['json']
        if distgit_opt is None:
            assert 'distgit' not in json
        else:
            assert json['distgit'] == distgit_opt

        assert json['scmurl'] == 'http://test.yaml'

    @pytest.mark.parametrize('distgit_opt', [None, 'fedora'])
    @mock.patch('copr.v3.requests.requests.request')
    def test_module_dist_git_choice_upload(self, request, distgit_opt):
        proxy = ModuleProxy(self.config_auth)
        proxy.build_from_file('owner', 'project',
                              self.yaml_file,
                              distgit=distgit_opt)

        assert len(request.call_args_list) == 1
        call = request.call_args_list[0]
        kwargs = call[1]
        json = kwargs['json']

        assert json is None

        # ('json', 'jsonstr', 'application/json')
        json_encoded = kwargs['data'].encoder.fields['json']
        json = loads(json_encoded[1])

        if distgit_opt is None:
            assert json is None
        else:
            assert json['distgit'] == distgit_opt
