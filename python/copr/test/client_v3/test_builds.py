import mock
from requests import Response
from copr.v3 import BuildProxy
from copr.v3.requests import Request


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
