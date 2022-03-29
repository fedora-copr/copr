from requests import Response
from copr.test import mock
from copr.v3.requests import Request, munchify


class TestResponse(object):
    def test_munchify(self):
        response = mock.Mock(spec=Response)
        response.json.return_value = {"id": 1, "foo": "bar"}
        response.headers = {"Status": "200 OK"}

        entity = munchify(response)
        assert entity.id == 1
        assert entity.foo == "bar"
        assert entity.__response__ == response
        assert entity.__response__.headers["Status"] == "200 OK"
        assert entity.__response__.json()["foo"] == "bar"


class TestRequest(object):
    def test_endpoint_url(self):
        r1 = Request(api_base_url="http://copr/api_3")
        assert r1.endpoint_url("foo") == "http://copr/api_3/foo"

        # Leading and/or trailing slash should not be a problem
        r2 = Request(api_base_url="http://copr/api_3/")
        assert r2.endpoint_url("/foo/bar") == "http://copr/api_3/foo/bar"

    @mock.patch('requests.Session.request')
    def test_send(self, request):
        req1 = Request(api_base_url="http://copr/api_3")
        resp1 = req1.send(endpoint="foo")

        request.assert_called_once()
        args, kwargs = request.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["url"] == "http://copr/api_3/foo"
