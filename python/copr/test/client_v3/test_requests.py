from requests import Response
from requests_toolbelt.multipart.encoder import MultipartEncoderMonitor
from copr.test import mock
from copr.v3.requests import FileRequest, Request, munchify


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


class TestFileRequest(object):
    def test_request_params_dict_files(self):
        # a single file per field name -- the traditional, backward
        # compatible shape
        req = FileRequest(
            api_base_url="http://copr/api_3",
            files={"pkgs": ("f.rpm", b"data", "application/x-rpm")},
        )
        # pylint: disable-next=protected-access
        params = req._request_params(endpoint="foo", method="POST", data={"a": 1})

        assert isinstance(params["data"], MultipartEncoderMonitor)
        assert params["json"] is None
        fields = params["data"].encoder.fields
        assert fields["pkgs"] == ("f.rpm", b"data", "application/x-rpm")
        assert fields["json"][0] == "json"

    def test_request_params_list_files(self):
        # multiple files under the same field name (e.g. several RPMs
        # uploaded via "pkgs") require a list-of-tuples instead of a dict,
        # since a dict can't hold duplicate keys
        req = FileRequest(
            api_base_url="http://copr/api_3",
            files=[
                ("pkgs", ("f1.rpm", b"data1", "application/x-rpm")),
                ("pkgs", ("f2.rpm", b"data2", "application/x-rpm")),
                ("srpm", ("f.src.rpm", b"data3", "application/x-rpm")),
            ],
        )
        # pylint: disable-next=protected-access
        params = req._request_params(endpoint="foo", method="POST", data={"a": 1})

        assert isinstance(params["data"], MultipartEncoderMonitor)
        fields = params["data"].encoder.fields
        names = [name for name, _value in fields]
        assert names.count("pkgs") == 2
        assert names.count("srpm") == 1
        assert names.count("json") == 1
