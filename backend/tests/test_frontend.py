# coding: utf-8

from munch import Munch
from requests import Response

from copr_common.request import RequestRetryError
from copr_backend.frontend import FrontendClient
from copr_backend.exceptions import FrontendClientException

from unittest import mock
from unittest.mock import MagicMock
import pytest

@pytest.yield_fixture
def post_req():
    with mock.patch("copr_common.request.post") as obj:
        yield obj

@pytest.fixture(scope='function', params=['get', 'post', 'put'])
def f_request_method(request):
    'mock the requests.{get,post,put} method'
    with mock.patch("copr_common.request.{}".format(request.param)) as ctx:
        ctx.return_value.headers = {
            "Copr-FE-BE-API-Version": "666",
        }
        yield (request.param, ctx)


@pytest.yield_fixture
def mc_time():
    with mock.patch("copr_common.request.time") as obj:
        yield obj


class TestFrontendClient(object):

    @staticmethod
    def _get_fake_response():
        resp = Munch()
        resp.headers = {
            "Copr-FE-BE-API-Version": "666",
        }
        resp.status_code = 200
        resp.data = "ok\n"
        return resp

    def setup_method(self, method):
        self.opts = Munch(
            frontend_base_url="http://example.com/",
            frontend_auth="12345678",
        )
        self.fc = FrontendClient(self.opts)

        self.data = {
            "foo": "bar",
            "bar": [1, 3, 5],
        }
        self.url_path = "sub_path"

        self.build_id = 12345
        self.task_id = "12345-fedora-20-x86_64"
        self.chroot_name = "fedora-20-x86_64"

    @pytest.fixture
    def mask_frontend_request(self):
        with mock.patch("copr_common.request.SafeRequest._send_request") as obj:
            yield obj

    def test_post_to_frontend(self, f_request_method):
        name, method = f_request_method
        method.return_value.status_code = 200
        self.fc.send(self.url_path, method=name, data=self.data)
        assert method.called

    def test_post_to_frontend_wrappers(self, f_request_method):
        name, method = f_request_method
        method.return_value.status_code = 200

        call = getattr(self.fc, name)
        if name == 'get':
            call(self.url_path)
        else:
            call(self.url_path, self.data)

        assert method.called

    def test_post_to_frontend_repeated_first_try_ok(self, mask_frontend_request, mc_time):
        mc_time.time.return_value = 0
        response = self._get_fake_response()
        mask_frontend_request.return_value = response
        assert self.fc.post(self.data, self.url_path) == response
        assert not mc_time.sleep.called

    def test_post_to_frontend_repeated_second_try_ok(self, f_request_method,
            mask_frontend_request, mc_time):
        method_name, method = f_request_method

        response = self._get_fake_response()
        mask_frontend_request.side_effect = [
            RequestRetryError(),
            response,
        ]
        mc_time.time.return_value = 0
        assert self.fc.send(
            self.url_path,
            data=self.data,
            method=method_name
        ) == response
        assert mc_time.sleep.called

    def test_post_to_frontend_err_400(self, post_req, mc_time):
        response = Response()
        response.status_code = 404
        response.reason = 'NOT FOUND'

        post_req.side_effect = [
            RequestRetryError(),
            response,
        ]

        mc_time.time.return_value = 0
        with pytest.raises(FrontendClientException):
            assert self.fc.post(self.data, self.url_path) == response
        assert mc_time.sleep.called

    def test_post_to_frontend_repeated_all_attempts_failed(self,
            mask_frontend_request, caplog, mc_time):
        mc_time.time.side_effect = [0, 0, 5, 5+10, 5+10+15, 5+10+15+20, 1000]
        mask_frontend_request.side_effect = RequestRetryError()
        with pytest.raises(FrontendClientException):
            self.fc.post(self.data, self.url_path)
        assert mc_time.sleep.call_args_list == [mock.call(x) for x in [5, 10, 15, 20, 25]]
        records = [x for x in caplog.records if "Retry request" in x.msg]
        assert len(records) == 5

    def test_post_to_frontend_repeated_indefinitely(self,
            mask_frontend_request, caplog, mc_time):
        mc_time.time.return_value = 1
        self.fc.try_indefinitely = True
        mask_frontend_request.side_effect = [RequestRetryError() for _ in range(100)] \
                             + [FrontendClientException()] # e.g. 501 eventually
        with pytest.raises(FrontendClientException):
            self.fc.post(self.data, self.url_path)
        assert mc_time.sleep.called
        records = [x for x in caplog.records if "Retry request" in x.msg]
        assert len(records) == 100

    def test_retries_on_outdated_frontend(self, mask_frontend_request, caplog):
        response = self._get_fake_response()
        response.headers["Copr-FE-BE-API-Version"] = "0"
        mask_frontend_request.side_effect = [
            response for _ in range(100)] + [Exception("sorry")]
        with pytest.raises(Exception):
            self.fc.try_indefinitely = True
            self.fc.post(self.url_path, self.data)
        assert len(mask_frontend_request.call_args_list) == 101
        assert "Sending POST request to frontend" in caplog.records[0].getMessage()
        assert "Copr FE/BE API is too old on Frontend" in caplog.records[1].msg

    def test_update(self):
        ptfr = MagicMock()
        self.fc.post = ptfr
        self.fc.update(self.data)
        assert ptfr.call_args == mock.call("update", self.data)

    def test_starting_build(self):
        ptfr = MagicMock()
        self.fc.post = ptfr
        for val in [True, False]:
            ptfr.return_value.json.return_value = {"can_start": val}

            assert self.fc.starting_build(self.data) == val

    def test_starting_build_err(self):
        ptfr = MagicMock()
        self.fc.post = ptfr

        with pytest.raises(FrontendClientException):
            self.fc.starting_build(self.data)

    def test_starting_build_err_2(self):
        ptfr = MagicMock()
        self.fc.post = ptfr
        ptfr.return_value.json.return_value = {}

        with pytest.raises(FrontendClientException):
            self.fc.starting_build(self.data)

    def test_reschedule_build(self):
        ptfr = MagicMock()
        self.fc.post = ptfr
        self.fc.reschedule_build(self.build_id, self.task_id, self.chroot_name)
        expected = mock.call('reschedule_build_chroot', {
            'build_id': self.build_id,
            'task_id': self.task_id,
            'chroot': self.chroot_name,
        })
        assert ptfr.call_args == expected
