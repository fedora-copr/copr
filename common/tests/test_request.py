import logging
from unittest import TestCase
from requests import RequestException
from copr_common.request import SafeRequest, RequestRetryError
from . import mock


class TestStringMethods(TestCase):

    def setUp(self):
        self.url = "http://example.com/"
        self.data = {
            "foo": "bar",
            "bar": [1, 3, 5],
        }
        self.log = logging.getLogger("testlog")

    @mock.patch("copr_common.request.requests.request")
    def test_send_request_not_200(self, post_req):
        post_req.return_value.status_code = 501
        with self.assertRaises(RequestRetryError):
            request = SafeRequest(log=self.log)
            request._send_request(self.url, "post", self.data)
        self.assertTrue(post_req.called)

    @mock.patch("copr_common.request.requests.request")
    def test_send_request_post_error(self, post_req):
        post_req.side_effect = RequestException()
        with self.assertRaises(RequestRetryError):
            request = SafeRequest(log=self.log)
            request._send_request(self.url, "post", self.data)
        self.assertTrue(post_req.called)
