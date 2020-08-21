"""
Test for adding packages
"""

import mock
import pytest

from copr.v3 import Client
from copr.test.test_client import config_location


@pytest.mark.parametrize('method_name', ['add', 'edit'])
@mock.patch("copr.v3.proxies.package.Request")
def test_package_distgit(request, method_name):
    mock_client = Client.create_from_config_file(config_location)
    method = getattr(mock_client.package_proxy, method_name)
    method("fooUser", "test", "mock", "distgit",
           {"committish": "master", "distgit": "fedora"})
    assert len(request.call_args_list) == 1
    call = request.call_args_list[0]
    endpoint = call[0][0]
    args = call[1]
    assert args['method'] == 'POST'
    base_url = "/package/{0}".format(method_name)
    assert endpoint == base_url + "/{ownername}/{projectname}/{package_name}/{source_type_text}"
    params = args['params']
    assert params == {'ownername': 'fooUser', 'projectname': 'test',
                      'package_name': 'mock', 'source_type_text': 'distgit'}
    assert args['data'] == {'committish': 'master', 'distgit': 'fedora',
                            'package_name': 'mock'}
