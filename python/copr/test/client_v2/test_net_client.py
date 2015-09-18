# coding: utf-8

import os
import copy
import tarfile
import tempfile
import shutil
import time

import six
import sys
import json

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

import pytest

from copr.client_v2.net_client import NetClient, RequestError


@pytest.yield_fixture
def mc_request():
    with mock.patch('copr.client_v2.net_client.request') as handle:
        yield handle


class TestNetClient(object):

    def setup_method(self, method):
        # print(sys.path)

        self.base_response = MagicMock()
        self.base_response.status_code = 200
        self.content = {
            "msg": "Lorem ipsum dolor sit amet"
        }
        self.base_response.content = json.dumps(self.content)
        self.base_response.headers = {
            "content-type": "application/json"
        }

        self.login = u"foo"
        self.password = u"bar"
        self.base_url = "http://example.com/abcd"

        self.nc = NetClient()
        self.nc_with_auth = NetClient(self.login, self.password)

    def test_get_simple(self, mc_request):
        mc_request.return_value = self.base_response
        res = self.nc.request(self.base_url)
        # import ipdb; ipdb.set_trace()
        assert res.status_code == self.base_response.status_code
        assert res.json == self.content
        assert res.headers == self.base_response.headers

    def test_unsupported_method(self, mc_request):
        with pytest.raises(RequestError) as exc_info:
            self.nc.request(self.base_url, method="non_existing_method")

        # some coverage for Request error
        s = str(exc_info.value)
        with pytest.raises(ValueError):
            # import ipdb; ipdb.set_trace()
            x = exc_info.value.response_json
