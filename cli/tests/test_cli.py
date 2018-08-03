import os
import argparse
from collections import defaultdict
import json
from pprint import pprint
import pytest

import six
import time
import copr
from copr.client.parsers import ProjectListParser, CommonMsgErrorOutParser
from copr.client.responses import CoprResponse
from copr.exceptions import CoprConfigException, CoprNoConfException, \
    CoprRequestException, CoprUnknownResponseException, CoprException, \
    CoprBuildException
from copr.client import CoprClient
import copr_cli
from copr_cli.main import no_config_warning


def exit_wrap(value):
    if type(value) == int:
        return value
    else:
        return value.code


if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock
#
# import logging
#
# logging.basicConfig(
#     level=logging.INFO,
#     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )
#
# log = logging.getLogger()
# log.info("Logger initiated")

from copr_cli import main


def test_parse_name():
    assert main.parse_name("foo") == (None, "foo")
    assert main.parse_name("frostyx/foo") == ("frostyx", "foo")
    assert main.parse_name("@copr/foo") == ("@copr", "foo")


@mock.patch('copr_cli.main.CoprClient')
def test_error_keyboard_interrupt(mock_cc, capsys):
    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.side_effect = KeyboardInterrupt()
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 1
    stdout, stderr = capsys.readouterr()
    assert "Interrupted by user" in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_error_copr_request(mock_cc, capsys):
    error_msg = "error message"

    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.side_effect = CoprRequestException(error_msg)
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 1
    stdout, stderr = capsys.readouterr()
    assert "Something went wrong" in stderr
    assert error_msg in stderr


@mock.patch('copr_cli.main.setup_parser')
@mock.patch('copr_cli.main.CoprClient')
def test_error_argument_error(mock_cc, mock_setup_parser, capsys):
    error_msg = "error message"

    mock_client = MagicMock(no_config=False)
    mock_cc.create_from_file_config.return_value = mock_client

    mock_setup_parser.return_value.parse_args.side_effect = \
        argparse.ArgumentTypeError(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 2
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_error_no_args(mock_cc, capsys):
    mock_client = MagicMock(no_config=False)
    mock_cc.create_from_file_config.return_value = mock_client

    for func_name in ["status", "build", "delete", "create"]:
        with pytest.raises(SystemExit) as err:
            main.main(argv=[func_name])

        assert exit_wrap(err.value) == 2

        stdout, stderr = capsys.readouterr()
        assert "usage: copr" in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_error_copr_common_exception(mock_cc, capsys):
    error_msg = "error message"

    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.side_effect = \
        CoprException(error_msg)
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 3
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_error_copr_build_exception(mock_cc, capsys):
    error_msg = "error message"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.side_effect = \
        CoprBuildException(error_msg)
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["build", "prj1", "src1"])

    assert exit_wrap(err.value) == 4
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_error_copr_unknown_response(mock_cc, capsys):
    error_msg = "error message"

    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.side_effect = \
        CoprUnknownResponseException(error_msg)
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 5
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_cancel_build_no_config(mock_cc, capsys):
    mock_cc.create_from_file_config.side_effect = CoprNoConfException()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["cancel", "123400"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()

    assert "Error: Operation requires api authentication" in err
    assert "File '~/.config/copr' is missing or incorrect" in err

    expected_warning = no_config_warning.format("~/.config/copr")
    assert expected_warning in err


@mock.patch('copr_cli.main.CoprClient')
def test_cancel_build_response(mock_cc, capsys):
    response_status = "foobar"

    mock_client = MagicMock(no_config=False, )
    mock_client.cancel_build.return_value = MagicMock(status=response_status)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=["cancel", "123"])
    out, err = capsys.readouterr()
    assert "{0}\n".format(response_status) in out


def read_res(name):
    dirpath = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(dirpath, "resources", name)
    return open(filepath).read()


@mock.patch('copr_cli.main.CoprClient')
def test_list_project(mock_cc, capsys):
    response_data = json.loads(read_res('list_projects_response.json'))
    expected_output = read_res('list_projects_expected.txt')

    # no config
    mock_cc.create_from_file_config.side_effect = CoprNoConfException()
    mocked_client = MagicMock(CoprClient(no_config=True))

    control_response = CoprResponse(client=None, method="", data=response_data,
                                    parsers=[ProjectListParser, CommonMsgErrorOutParser])
    mocked_client.get_projects_list.return_value = control_response
    mock_cc.return_value = mocked_client

    main.main(argv=["list", "rhscl"])

    out, err = capsys.readouterr()
    assert expected_output in out

    expected_warning = no_config_warning.format("~/.config/copr")
    assert expected_warning in err


@mock.patch('copr_cli.main.CoprClient')
def test_list_project_no_username(mock_cc, capsys):
    mock_cc.create_from_file_config.side_effect = CoprNoConfException()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["list"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()
    assert "Pass username to command or create `~/.config/copr`" in err


@mock.patch('copr_cli.main.CoprClient')
def test_list_project_no_username2(mock_cc, capsys):
    mock_cc.create_from_file_config.return_value = CoprClient()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["list"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()
    assert "Pass username to command or add it to `~/.config/copr`" in err


@mock.patch('copr_cli.main.CoprClient')
def test_list_project_error_msg(mock_cc, capsys):
    mock_client = MagicMock(no_config=False, username="dummy")
    mock_cc.create_from_file_config.return_value = mock_client

    mock_response = MagicMock(response=CoprResponse(None, None, None),
                              output="notok", error="error_msg",
                              projects_list=[])

    mock_client.get_projects_list.return_value = mock_response
    main.main(argv=["list", "projectname"])

    out, err = capsys.readouterr()
    assert "error_msg" in err


@mock.patch('copr_cli.main.CoprClient')
def test_list_project_empty_list(mock_cc, capsys):
    mock_client = MagicMock(no_config=False, username="dummy")
    mock_cc.create_from_file_config.return_value = mock_client

    mock_response = MagicMock(response=CoprResponse(None, None, None),
                              output="ok", projects_list=[])

    mock_client.get_projects_list.return_value = mock_response
    main.main(argv=["list", "projectname"])

    out, err = capsys.readouterr()
    assert "error" not in out
    assert "No copr retrieved for user: dummy"


@mock.patch('copr_cli.main.CoprClient')
def test_status_response(mock_cc, capsys):
    response_status = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.return_value = \
        MagicMock(status=response_status)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=["status", "123"])
    out, err = capsys.readouterr()
    assert "{0}\n".format(response_status) in out


@mock.patch('copr_cli.main.CoprClient')
def test_debug_by_status_response(mock_cc, capsys):
    response_status = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.return_value = \
        MagicMock(status=response_status)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=["--debug", "status", "123"])
    stdout, stderr = capsys.readouterr()
    assert "{0}\n".format(response_status) in stdout
    assert "Debug log enabled " in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_status_response_no_args(mock_cc, capsys):
    mock_client = MagicMock(no_config=False)
    mock_cc.create_from_file_config.return_value = mock_client

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status"])

    assert exit_wrap(err.value) == 2

    stdout, stderr = capsys.readouterr()
    assert "usage: copr" in stderr


@mock.patch('copr_cli.main.CoprClient')
def test_delete_project(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.delete_project.return_value = \
        MagicMock(message=response_message)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=["delete", "foo"])
    out, err = capsys.readouterr()
    assert "{0}\n".format(response_message) in out


@mock.patch('copr_cli.main.subprocess')
@mock.patch('copr_cli.main.CoprClient')
def test_download_build(mock_cc, mock_sp, capsys):
    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.return_value = \
        MagicMock(
            data={"chroots": {
                u'epel-6-x86_64': u'succeeded', u'epel-6-i386': u'succeeded'
            }},
            results="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20",
            results_by_chroot={
                u'epel-6-x86_64': u'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20',
                u'epel-6-i386': u'http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20',
            }
        )
    mock_cc.create_from_file_config.return_value = mock_client

    mock_sp.call.return_value = None
    main.main(argv=["download-build", "foo"])
    stdout, stderr = capsys.readouterr()

    expected_sp_call_args = [
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', "'index.html*'",
            '-P', './epel-6-x86_64', '--cut-dirs', '6',
            'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20'
        ]),
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', "'index.html*'",
            '-P', './epel-6-i386', '--cut-dirs', '6',
            'http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20'
        ])
    ]

    for call_args_list in mock_sp.call.call_args_list:
        assert call_args_list in expected_sp_call_args


@mock.patch('copr_cli.main.subprocess')
@mock.patch('copr_cli.main.CoprClient')
def test_download_build_select_chroot(mock_cc, mock_sp, capsys):
    mock_client = MagicMock(no_config=False)
    mock_client.get_build_details.return_value = \
        MagicMock(
            data={"chroots": {
                u'epel-6-x86_64': u'succeeded', u'epel-6-i386': u'succeeded'
            }},
            results="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20",
            results_by_chroot={
                u'epel-6-x86_64': u'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20',
                u'epel-6-i386': u'http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20',
            }
        )
    mock_cc.create_from_file_config.return_value = mock_client

    mock_sp.call.return_value = None
    main.main(argv=["download-build", "foo", "-r", "epel-6-x86_64"])
    stdout, stderr = capsys.readouterr()
    expected_sp_call_args = [
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', "'index.html*'",
            '-P', u'./epel-6-x86_64', '--cut-dirs', '6',
            'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20'
        ]),
    ]

    assert mock_sp.call.call_args_list == expected_sp_call_args


@mock.patch('copr_cli.main.CoprClient')
def test_create_project(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_project.return_value = \
        MagicMock(message=response_message)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=[
        "create", "foo",
        "--chroot", "f20", "--chroot", "f21",
        "--description", "desc string",
        "--instructions", "instruction string",
        "--repo", "repo1", "--repo", "repo2",
        "--initial-pkgs", "pkg1"
    ])

    stdout, stderr = capsys.readouterr()

    mock_client.create_project.assert_called_with(auto_prune=True,
        username=None, persistent=False, projectname="foo", description="desc string",
        instructions="instruction string", chroots=["f20", "f21"],
        repos=["repo1", "repo2"], initial_pkgs=["pkg1"],
        unlisted_on_hp=None, disable_createrepo=None, enable_net=False,
        use_bootstrap_container=None)

    assert "{0}\n".format(response_message) in stdout


@mock.patch('copr_cli.main.CoprClient')
def test_create_build_no_wait_ok(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(output="ok", message=response_message)

    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=[
        "build", "--nowait",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert response_message in stdout
    assert "Created builds" in stdout

    assert not mock_client._watch_build.called


@mock.patch('copr_cli.main.CoprClient')
def test_create_build_no_wait_error(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(output="notok", error=response_message)

    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=[
        "build", "--nowait",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert response_message in stderr

    assert not mock_client._watch_build.called


@mock.patch('copr_cli.main.time')
@mock.patch('copr_cli.main.CoprClient')
def test_create_build_wait_succeeded_no_sleep(mock_cc, mock_time, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(
        output="ok",
        message=response_message,
        builds_list=[
            MagicMock(build_id=x)
            for x in range(3)
        ])
    mock_client.get_build_details.return_value = MagicMock(
        status="succeeded", output="ok"
    )
    mock_cc.create_from_file_config.return_value = mock_client
    main.main(argv=[
        "build",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()

    assert response_message in stdout
    assert "Created builds" in stdout
    assert "Watching build" in stdout
    assert not mock_time.sleep.called


@mock.patch('copr_cli.main.CoprClient')
def test_create_build_wait_error_status(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(
        output="ok",
        message=response_message,
        builds_list=[
            MagicMock(build_id=x)
            for x in ["1", "2", "3"]
        ])
    mock_client.get_build_details.return_value = MagicMock(
        output="notok"
    )
    mock_cc.create_from_file_config.return_value = mock_client
    with pytest.raises(SystemExit) as err:
        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])
        assert exit_wrap(err.value) == 1

    stdout, stderr = capsys.readouterr()
    assert response_message in stdout
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr_cli.main.CoprClient')
def test_create_build_wait_unknown_build_status(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(
        output="ok",
        message=response_message,
        builds_list=[
            MagicMock(build_id=x)
            for x in ["1", "2", "3"]
        ])
    mock_client.get_build_details.return_value = MagicMock(
        output="ok", status="unknown"
    )
    mock_cc.create_from_file_config.return_value = mock_client
    with pytest.raises(SystemExit) as err:
        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])
        assert exit_wrap(err.value) == 1

    stdout, stderr = capsys.readouterr()
    assert response_message in stdout
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr_cli.main.CoprClient')
def test_create_build_wait_keyboard_interrupt(mock_cc, capsys):
    response_message = "foobar"

    mock_client = MagicMock(no_config=False)
    mock_client.create_new_build.return_value = MagicMock(
        output="ok",
        message=response_message,
        builds_list=[
            MagicMock(build_id=x)
            for x in ["1", "2", "3"]
        ])
    mock_client.get_build_details.side_effect = KeyboardInterrupt

    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=[
        "build",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert response_message in stdout
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr_cli.main.time')
@mock.patch('copr_cli.main.CoprClient')
class TestCreateBuild(object):
    def test_create_build_wait_succeeded_complex(self, mock_cc, mock_time, capsys):
        response_message = "foobar"

        mock_client = MagicMock(no_config=False)
        mock_client.create_new_build.return_value = MagicMock(
            output="ok",
            message=response_message,
            builds_list=[
                MagicMock(build_id=x)
                for x in range(3)
            ])

        self.stage = 0

        def incr(*args, **kwargs):
            self.stage += 1

        def result_map(build_id, *args, **kwargs):
            if self.stage == 0:
                return MagicMock(status="pending", output="ok")
            elif self.stage == 1:
                smap = {0: "pending", 1: "starting", 2: "running"}
                return MagicMock(status=smap[build_id], output="ok")
            elif self.stage == 2:
                smap = {0: "starting", 1: "running", 2: "succeeded"}
                return MagicMock(status=smap[build_id], output="ok")
            elif self.stage == 3:
                smap = {0: "skipped", 1: "succeeded", 2: "succeeded"}
                return MagicMock(status=smap[build_id], output="ok")

        mock_time.sleep.side_effect = incr

        mock_client.get_build_details.side_effect = result_map
        mock_cc.create_from_file_config.return_value = mock_client

        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])

        stdout, stderr = capsys.readouterr()

        assert response_message in stdout
        assert "Created builds" in stdout
        assert "Watching build" in stdout
        assert len(mock_time.sleep.call_args_list) == 3

    def test_create_build_wait_failed_complex(self, mock_cc, mock_time, capsys):
        response_message = "foobar"

        mock_client = MagicMock(no_config=False)
        mock_client.create_new_build.return_value = MagicMock(
            output="ok",
            message=response_message,
            builds_list=[
                MagicMock(build_id=x)
                for x in range(3)
            ])

        self.stage = 0

        def incr(*args, **kwargs):
            self.stage += 1

        def result_map(build_id, *args, **kwargs):
            if self.stage == 0:
                return MagicMock(status="pending", output="ok")
            elif self.stage == 1:
                smap = {0: "pending", 1: "starting", 2: "running"}
                return MagicMock(status=smap[build_id], output="ok")
            elif self.stage == 2:
                smap = {0: "failed", 1: "running", 2: "succeeded"}
                return MagicMock(status=smap[build_id], output="ok")
            elif self.stage == 3:
                smap = {0: "failed", 1: "failed", 2: "succeeded"}
                return MagicMock(status=smap[build_id], output="ok")

        mock_time.sleep.side_effect = incr

        mock_client.get_build_details.side_effect = result_map
        mock_cc.create_from_file_config.return_value = mock_client

        with pytest.raises(SystemExit) as err:
            main.main(argv=[
                "build",
                "copr_name", "http://example.com/pkgs.srpm"
            ])

        stdout, stderr = capsys.readouterr()

        assert response_message in stdout
        assert "Created builds" in stdout
        assert "Watching build" in stdout
        assert "Build(s) 0, 1 failed" in stderr
        assert len(mock_time.sleep.call_args_list) == 3
