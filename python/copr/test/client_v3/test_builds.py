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


@pytest.mark.parametrize("epoch,expected_data", [
    (None, {
        'ownername': 'praiskup', 'projectname': 'ping',
        'project_dirname': None, 'name': 'ping',
        'version': '1.0', 'release': '1',
        'chroots': ['fedora-40-x86_64'],
    }),
    (2, {
        'ownername': 'praiskup', 'projectname': 'ping',
        'project_dirname': None, 'name': 'ping',
        'version': '1.0', 'release': '1', 'epoch': 2,
        'chroots': ['fedora-40-x86_64'],
    }),
])
@mock.patch('copr.v3.proxies.Request.send')
def test_build_rpm_upload(send, epoch, expected_data):
    mock_client = Client.create_from_config_file(config_location)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tarball_file:
        kwargs = {
            "tarball_path": tarball_file.name,
            "name": "ping",
            "version": "1.0",
            "release": "1",
            "buildopts": {"chroots": ["fedora-40-x86_64"]},
        }
        if epoch is not None:
            kwargs["epoch"] = epoch
        mock_client.build_proxy.create_from_rpm_upload(
            "praiskup", "ping", **kwargs)
        assert len(send.call_args_list) == 1
        call = send.call_args_list[0]
        args = call[1]
        assert args['method'] == 'POST'
        assert args['endpoint'] == '/build/create/rpm-upload'
        assert args['data'] == expected_data


def test_build_rpm_upload_requires_tarball_path():
    mock_client = Client.create_from_config_file(config_location)
    with pytest.raises(CoprValidationException):
        mock_client.build_proxy.create_from_rpm_upload(
            "praiskup", "ping", name="ping", version="1.0", release="1")
