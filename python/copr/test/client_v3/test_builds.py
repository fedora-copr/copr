import mock
from requests import Response
from copr.v3 import Client, BuildProxy
from copr.v3.requests import Request

from copr.test import config_location


@mock.patch.object(Request, "send")
class TestBuildProxy(object):
    config = {"copr_url": "http://copr"}

    def test_get(self, send):
        response = mock.Mock(spec=Response)
        response.json.return_value = {"id": 1, "foo": "bar"}
        send.return_value = response

        build_proxy = BuildProxy(self.config)
        build = build_proxy.get(1)
        assert build.id == 1
        assert build.foo == "bar"


@mock.patch("copr.v3.proxies.build.Request")
def test_build_distgit(request):
    mock_client = Client.create_from_config_file(config_location)
    mock_client.build_proxy.create_from_distgit(
        "praiskup", "ping", "mock", committish="master",
    )
    assert len(request.call_args_list) == 1
    call = request.call_args_list[0]
    args = call[1]
    assert args['method'] == 'POST'
    assert args['endpoint'] == '/build/create/distgit'
    assert args['data'] == {
        'ownername': 'praiskup', 'projectname': 'ping',
        'distgit': None, 'namespace': None, 'package_name': 'mock',
        'committish': 'master', 'project_dirname': None}
