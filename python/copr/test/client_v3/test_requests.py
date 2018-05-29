import pytest
import mock
from copr.v3 import Response
from copr.v3 import Request
from copr.v3.requests import handle_errors, CoprRequestException

class TestResponse(object):
    def test_bar(self):
        r1 = Response()
        assert r1.data == {}
        assert r1.headers == {}

        r2 = Response(headers={"Status": "200 OK"}, data={"foo": "bar"})
        assert r2.data["foo"] == "bar"
        assert r2.headers["Status"] == "200 OK"

    def test_munchify(self):
        response = Response(headers={"Status": "200 OK"}, data={"id": 1, "foo": "bar"})
        entity = response.munchify()
        assert entity.id == 1
        assert entity.foo == "bar"
        assert entity.__response__ == response
        assert entity.__response__.headers["Status"] == "200 OK"
        assert entity.__response__.data["foo"] == "bar"


class TestRequest(object):
    def test_endpoint_url(self):
        r1 = Request(endpoint="foo", api_base_url="http://copr/api_3")
        assert r1.endpoint_url == "http://copr/api_3/foo"

        # Leading and/or trailing slash should not be a problem
        r2 = Request(endpoint="/foo/bar", api_base_url="http://copr/api_3/")
        assert r2.endpoint_url == "http://copr/api_3/foo/bar"

    @mock.patch("requests.request")
    def test_send(self, request):
        req1 = Request(endpoint="foo", api_base_url="http://copr/api_3")
        resp1 = req1.send()

        request.assert_called_once()
        args, kwargs = request.call_args
        assert kwargs["method"] == "GET"
        assert kwargs["url"] == "http://copr/api_3/foo"

        assert isinstance(resp1, Response)
