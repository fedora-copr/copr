# coding: utf-8
import six
from copr.client_v2.handlers import ProjectHandle, ProjectChrootHandle

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

import pytest

from copr.client_v2.client import CoprClient


class TestClientV2(object):
    def setup_method(self, method):
        self.login = u"foo"
        self.token = u"bar"
        self.root_url = "http://example.com/abcd"

        self.nc = MagicMock()

        self.root_json = {
            "_links": {
                "mock_chroots": {
                    "href": "/api_2/mock_chroots"
                },
                "self": {
                    "href": "/api_2/"
                },
                "projects": {
                    "href": "/api_2/projects"
                },
                "builds": {
                    "href": "/api_2/builds"
                },
                "build_tasks": {
                    "href": "/api_2/build_tasks"
                }
            }
        }
        self.response = MagicMock()

    @pytest.fixture
    def tc(self):
        # configures test client
        response = MagicMock()
        response.json = self.root_json
        self.nc.request.return_value = response

        client = CoprClient(self.nc, self.root_url, no_config=True)
        client.post_init()

        return client

    def test_create_from_empty_params(self):
        with mock.patch('copr.client_v2.client.NetClient') as handle:
            self.response.json = self.root_json
            handle.return_value.request.return_value = self.response
            CoprClient.create_from_params()

            assert handle.called
            assert handle.call_args == mock.call(None, None)

    def test_create_from_params(self):
        with mock.patch('copr.client_v2.client.NetClient') as handle:
            self.response.json = self.root_json
            handle.return_value.request.return_value = self.response
            CoprClient.create_from_params(
                self.root_url, self.login, self.token)

            assert handle.called
            assert handle.call_args == mock.call(self.login, self.token)

    # todo: def test_create_from_file_config

    def test_post_init(self):
        tc = CoprClient(self.nc, self.root_url, no_config=True)
        # import ipdb; ipdb.set_trace()

        self.response.json = self.root_json
        self.nc.request.return_value = self.response

        tc.post_init()
        assert tc._post_init_done

        assert isinstance(tc.projects, ProjectHandle)
        assert isinstance(tc.project_chroots, ProjectChrootHandle)

    def test_fixture_tc(self, tc):
        pass
