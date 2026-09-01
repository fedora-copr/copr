import tempfile

import pytest
from requests import Response
from copr.v3 import Client, BuildProxy
from copr.v3.exceptions import CoprValidationException
from copr.v3.requests import Request

from copr.test import config_location, mock


@mock.patch.object(Request, "send")
class TestBuildProxy(object):
    config = {"copr_url": "http://copr", "login": "test", "token": "test"}

    def test_get(self, send):
        response = mock.Mock(spec=Response)
        response.json.return_value = {"id": 1, "foo": "bar"}
        send.return_value = response

        build_proxy = BuildProxy(self.config)
        build = build_proxy.get(1)
        assert build.id == 1
        assert build.foo == "bar"


@mock.patch('copr.v3.proxies.Request.send')
def test_build_distgit(send):
    mock_client = Client.create_from_config_file(config_location)
    mock_client.build_proxy.create_from_distgit(
        "praiskup", "ping", "mock", committish="master",
    )
    assert len(send.call_args_list) == 1
    call = send.call_args_list[0]
    args = call[1]
    assert args['method'] == 'POST'
    assert args['endpoint'] == '/build/create/distgit'
    assert args['data'] == {
        'ownername': 'praiskup', 'projectname': 'ping',
        'distgit': None, 'namespace': None, 'package_name': 'mock',
        'committish': 'master', 'project_dirname': None}


@mock.patch('copr.v3.proxies.Request.send')
def test_build_rpm_upload(send):
    mock_client = Client.create_from_config_file(config_location)
    with tempfile.NamedTemporaryFile(suffix=".rpm") as rpm_file:
        mock_client.build_proxy.create_from_rpm_upload(
            "praiskup", "ping", paths=[rpm_file.name],
            buildopts={"chroots": ["fedora-40-x86_64"]},
        )
        assert len(send.call_args_list) == 1
        call = send.call_args_list[0]
        args = call[1]
        assert args['method'] == 'POST'
        assert args['endpoint'] == '/build/create/rpm-upload'
        assert args['data'] == {
            'ownername': 'praiskup', 'projectname': 'ping',
            'project_dirname': None, 'name': None,
            'chroots': ['fedora-40-x86_64'], 'sha256': None}


@mock.patch('copr.v3.proxies.Request.send')
def test_build_rpm_upload_multi(send):
    mock_client = Client.create_from_config_file(config_location)
    with tempfile.NamedTemporaryFile(suffix=".rpm") as rpm1, \
            tempfile.NamedTemporaryFile(suffix=".rpm") as rpm2, \
            tempfile.NamedTemporaryFile(suffix=".src.rpm") as srpm, \
            tempfile.NamedTemporaryFile(suffix=".log") as log:
        mock_client.build_proxy.create_from_rpm_upload(
            "praiskup", "ping", paths=[rpm1.name, rpm2.name],
            name="ping", srpm_path=srpm.name, log_paths=[log.name],
            buildopts={"chroots": ["fedora-40-x86_64"]},
        )
        assert len(send.call_args_list) == 1
        call = send.call_args_list[0]
        args = call[1]
        assert args['method'] == 'POST'
        assert args['endpoint'] == '/build/create/rpm-upload'
        assert args['data'] == {
            'ownername': 'praiskup', 'projectname': 'ping',
            'project_dirname': None, 'name': 'ping',
            'chroots': ['fedora-40-x86_64'], 'sha256': None}


def test_build_rpm_upload_requires_paths():
    mock_client = Client.create_from_config_file(config_location)
    with pytest.raises(CoprValidationException):
        mock_client.build_proxy.create_from_rpm_upload("praiskup", "ping")
