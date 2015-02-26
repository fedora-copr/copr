# coding: utf-8

import multiprocessing

from bunch import Bunch
from requests import RequestException
import six

from backend.frontend import FrontendClient


if six.PY3:
    from unittest import mock
    from unittest.mock import patch, MagicMock
else:
    import mock
    from mock import MagicMock

import pytest


@pytest.yield_fixture
def post_req():
    with mock.patch("backend.frontend.post") as obj:
        yield obj


@pytest.yield_fixture
def mc_time():
    with mock.patch("backend.frontend.time") as obj:
        yield obj

class TestFrontendClient(object):

    def setup_method(self, method):
        self.opts = Bunch(
            frontend_url="http://example.com/",
            frontend_auth="12345678",
        )
        self.events = multiprocessing.Queue()
        self.fc = FrontendClient(self.opts, self.events)

        self.data = {
            "foo": "bar",
            "bar": [1, 3, 5],
        }
        self.url_path = "sub_path"

        self.build_id = 12345
        self.chroot_name = "fedora-20-x86_64"

    @pytest.fixture
    def mask_post_to_fe(self):
        self.ptf = MagicMock()
        self.fc._post_to_frontend = self.ptf

    def test_post_to_frontend(self, post_req):
        post_req.return_value.status_code = 200
        self.fc._post_to_frontend(self.data, self.url_path)

        assert post_req.called

    def test_post_to_frontend_not_200(self, post_req):
        post_req.return_value.status_code = 501
        with pytest.raises(RequestException):
            self.fc._post_to_frontend(self.data, self.url_path)

        assert post_req.called

    def test_post_to_frontend_post_error(self, post_req):
        post_req.side_effect = RequestException()
        with pytest.raises(RequestException):
            self.fc._post_to_frontend(self.data, self.url_path)

        assert post_req.called

    def test_post_to_frontend_repeated_first_try_ok(self, mask_post_to_fe, mc_time):
        response = "ok\n"
        self.ptf.return_value = response

        assert self.fc._post_to_frontend_repeatedly(self.data, self.url_path) == response
        assert not mc_time.sleep.called

    def test_post_to_frontend_repeated_second_try_ok(self, mask_post_to_fe, mc_time):
        response = "ok\n"
        self.ptf.side_effect = [
            RequestException(),
            response,
        ]

        assert self.fc._post_to_frontend_repeatedly(self.data, self.url_path) == response
        assert mc_time.sleep.called

    def test_post_to_frontend_repeated_all_attempts_failed(self, mask_post_to_fe, mc_time):
        self.ptf.side_effect = RequestException()

        with pytest.raises(RequestException):
            self.fc._post_to_frontend_repeatedly(self.data, self.url_path)

        assert mc_time.sleep.called

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

            assert self.fc.starting_build(self.build_id, self.chroot_name) == val

    def test_starting_build_err(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr

        with pytest.raises(RequestException):
            self.fc.starting_build(self.build_id, self.chroot_name)

    def test_starting_build_err_2(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        ptfr.return_value.json.return_value = {}

        with pytest.raises(RequestException):
            self.fc.starting_build(self.build_id, self.chroot_name)

    def test_reschedule_build(self):
        ptfr = MagicMock()
        self.fc._post_to_frontend_repeatedly = ptfr
        self.fc.reschedule_build(self.build_id, self.chroot_name)
        expected = mock.call({'build_id': self.build_id, 'chroot': self.chroot_name},
                             'reschedule_build_chroot')
        assert ptfr.call_args == expected
