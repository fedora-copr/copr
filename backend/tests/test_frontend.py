# coding: utf-8

import multiprocessing

from munch import Munch
from requests import RequestException, Response

from backend.frontend import (FrontendClient, FrontendClientRetryError,
                              SLEEP_INCREMENT_TIME)
from backend.exceptions import FrontendClientException

from unittest import mock
from unittest.mock import MagicMock
import pytest

@pytest.yield_fixture
def post_req():
    with mock.patch("backend.frontend.post") as obj:
        yield obj

@pytest.fixture(scope='function', params=['get', 'post', 'put'])
def f_request_method(request):
    'mock the requests.{get,post,put} method'
    with mock.patch("backend.frontend.{}".format(request.param)) as ctx:
        yield (request.param, ctx)


@pytest.yield_fixture
def mc_time():
    with mock.patch("backend.frontend.time") as obj:
        yield obj


class TestFrontendClient(object):

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
        self.f_r = MagicMock()
        self.fc._frontend_request = self.f_r

    def test_post_to_frontend(self, f_request_method):
        name, method = f_request_method
        method.return_value.status_code = 200
        self.fc._frontend_request(self.url_path, self.data, method=name)
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

    def test_post_to_frontend_not_200(self, post_req):
        post_req.return_value.status_code = 501
        with pytest.raises(FrontendClientRetryError):
            self.fc._frontend_request(self.url_path, self.data)

        assert post_req.called

    def test_post_to_frontend_post_error(self, post_req):
        post_req.side_effect = RequestException()
        with pytest.raises(FrontendClientRetryError):
            self.fc._frontend_request(self.url_path, self.data)

        assert post_req.called

    def test_post_to_frontend_repeated_first_try_ok(self, mask_frontend_request, mc_time):
        response = "ok\n"
        self.f_r.return_value = response
        mc_time.time.return_value = 0

        assert self.fc._post_to_frontend_repeatedly(self.data, self.url_path) == response
        assert not mc_time.sleep.called

    def test_post_to_frontend_repeated_second_try_ok(self, f_request_method,
            mask_frontend_request, mc_time):
        method_name, method = f_request_method

        response = "ok\n"
        self.f_r.side_effect = [
            FrontendClientRetryError(),
            response,
        ]
        mc_time.time.return_value = 0
        assert self.fc._frontend_request_repeatedly(
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
            FrontendClientRetryError(),
            response,
        ]

        mc_time.time.return_value = 0
        with pytest.raises(FrontendClientException):
            assert self.fc._post_to_frontend_repeatedly(self.data, self.url_path) == response
        assert mc_time.sleep.called

    @mock.patch('backend.frontend.BACKEND_TIMEOUT', 100)
    def test_post_to_frontend_repeated_all_attempts_failed(self,
            mask_frontend_request, caplog, mc_time):
        mc_time.time.side_effect = [0, 0, 5, 5+10, 5+10+15, 5+10+15+20, 1000]
        self.f_r.side_effect = FrontendClientRetryError()
        with pytest.raises(FrontendClientException):
            self.fc._post_to_frontend_repeatedly(self.data, self.url_path)
        assert mc_time.sleep.call_args_list == [mock.call(x) for x in [5, 10, 15, 20, 25]]
        assert len(caplog.records) == 5

    def test_post_to_frontend_repeated_indefinitely(self,
            mask_frontend_request, caplog, mc_time):
        mc_time.time.return_value = 1
        self.fc.try_indefinitely = True
        self.f_r.side_effect = [FrontendClientRetryError() for _ in range(100)] \
                             + [FrontendClientException()] # e.g. 501 eventually
        with pytest.raises(FrontendClientException):
            self.fc._post_to_frontend_repeatedly(self.data, self.url_path)
        assert mc_time.sleep.called
        assert len(caplog.records) == 100

    def test_reschedule_300(self, mask_frontend_request, post_req):
        response = Response()
        response.status_code = 302
        response.reason = 'whatever'
        post_req.side_effect = response
        with pytest.raises(FrontendClientException) as ex:
            self.fc.reschedule_all_running()
        assert 'Failed to reschedule builds' in str(ex)

    def test_update(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        self.fc.update(self.data)
        assert ptfr.call_args == mock.call(self.data, "update")

    def test_starting_build(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        for val in [True, False]:
            ptfr.return_value.json.return_value = {"can_start": val}

            assert self.fc.starting_build(self.data) == val

    def test_starting_build_err(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr

        with pytest.raises(FrontendClientException):
            self.fc.starting_build(self.data)

    def test_starting_build_err_2(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        ptfr.return_value.json.return_value = {}

        with pytest.raises(FrontendClientException):
            self.fc.starting_build(self.data)

    def test_reschedule_build(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        self.fc.reschedule_build(self.build_id, self.task_id, self.chroot_name)
        expected = mock.call({'build_id': self.build_id, 'task_id': self.task_id, 'chroot': self.chroot_name},
                             'reschedule_build_chroot')
        assert ptfr.call_args == expected
