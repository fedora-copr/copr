import mock
from copr.client_v3 import BuildProxy
from copr.client_v3 import Response
from copr.client_v3 import Request


@mock.patch.object(Request, "send")
class TestBuildProxy(object):
    config = {"copr_url": "http://copr"}

    def test_get(self, send):
        send.return_value = Response(data={"id": 1, "foo": "bar"})

        build_proxy = BuildProxy(self.config)
        build = build_proxy.get(1)
        assert build.id == 1
        assert build.foo == "bar"
