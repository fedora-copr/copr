import os
import argparse
import json
import pytest
import responses
from munch import Munch

import copr
from copr.exceptions import CoprUnknownResponseException, CoprBuildException
from copr_cli.main import no_config_warning, FrontendOutdatedCliException

from cli_tests_lib import mock, MagicMock, config as mock_config

def exit_wrap(value):
    if type(value) == int:
        return value
    else:
        return value.code


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

@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_parse_name(config_from_file):
    cmd = main.Commands(config_path=None)
    assert cmd.parse_name("foo") == (None, "foo")
    assert cmd.parse_name("frostyx/foo") == ("frostyx", "foo")
    assert cmd.parse_name("@copr/foo") == ("@copr", "foo")


@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_error_keyboard_interrupt(config_from_file, build_proxy_get, capsys):
    build_proxy_get.side_effect = KeyboardInterrupt()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 1
    stdout, stderr = capsys.readouterr()
    assert "Interrupted by user" in stderr

@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file')
def test_error_old_frontend(config_from_file, build_proxy_get, capsys):
    config_from_file.return_value = mock_config
    build_proxy_get.side_effect = FrontendOutdatedCliException("XXX")
    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])
    assert exit_wrap(err.value) == 5
    _, stderr = capsys.readouterr()
    assert "is older than XXX" in stderr

@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_error_copr_request(config_from_file, build_proxy_get, capsys):
    error_msg = "error message"
    build_proxy_get.side_effect = copr.v3.CoprRequestException(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 1
    stdout, stderr = capsys.readouterr()
    assert "Something went wrong" in stderr
    assert error_msg in stderr


@mock.patch('copr_cli.main.setup_parser')
def test_error_argument_error(mock_setup_parser, capsys):
    error_msg = "error message"

    mock_setup_parser.return_value.parse_args.side_effect = \
        argparse.ArgumentTypeError(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 2
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


def test_error_no_args(capsys):
    for func_name in ["status", "build", "delete", "create"]:
        with pytest.raises(SystemExit) as err:
            main.main(argv=[func_name])

        assert exit_wrap(err.value) == 2

        stdout, stderr = capsys.readouterr()
        assert "usage: copr" in stderr


@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_error_copr_common_exception(config_from_file, build_proxy_get, capsys):
    error_msg = "error message"
    build_proxy_get.side_effect = copr.v3.CoprException(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 3
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.Commands.action_build')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_error_copr_build_exception(config_from_file, action_build, capsys):
    error_msg = "error message"
    action_build.side_effect = CoprBuildException(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["build", "prj1", "src1"])

    assert exit_wrap(err.value) == 4
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.Commands.action_status')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_error_copr_unknown_response(config_from_file, action_status, capsys):
    error_msg = "error message"
    action_status.side_effect = CoprUnknownResponseException(error_msg)

    with pytest.raises(SystemExit) as err:
        main.main(argv=["status", "123"])

    assert exit_wrap(err.value) == 5
    stdout, stderr = capsys.readouterr()
    assert error_msg in stderr


@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_cancel_build_no_config(config_from_file, capsys):
    config_from_file.side_effect = copr.v3.CoprNoConfigException("Dude, your config is missing")

    with pytest.raises(SystemExit) as err:
        main.main(argv=["cancel", "123400"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()

    assert "Error: Operation requires api authentication" in err
    assert "File '~/.config/copr' is missing or incorrect" in err

    expected_warning = no_config_warning.format("~/.config/copr", "Dude, your config is missing")
    assert expected_warning in err


@mock.patch('copr.v3.proxies.build.BuildProxy.cancel')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_cancel_build_response(config_from_file, build_proxy_cancel, capsys):
    response_status = "foobar"
    build_proxy_cancel.return_value = MagicMock(state=response_status)

    main.main(argv=["cancel", "123"])
    out, err = capsys.readouterr()
    assert "{0}\n".format(response_status) in out


def read_res(name):
    dirpath = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(dirpath, "resources", name)
    return open(filepath).read()


@mock.patch('copr_cli.main.config_from_file')
@mock.patch('copr.v3.proxies.project.ProjectProxy.get_list')
def test_list_project(get_list, config_from_file, capsys):
    response_data = json.loads(read_res('list_projects_response.json'))
    expected_output = read_res('list_projects_expected.txt')

    # no config
    config_from_file.side_effect = copr.v3.CoprNoConfigException("Dude, your config is missing")
    control_response = [Munch(x) for x in response_data]
    get_list.return_value = control_response

    main.main(argv=["list", "rhscl"])
    out, err = capsys.readouterr()
    assert expected_output in out

    expected_warning = no_config_warning.format("~/.config/copr", "Dude, your config is missing")
    assert expected_warning in err

@responses.activate
@mock.patch("copr_cli.main.next_page")
@mock.patch('copr_cli.main.config_from_file')
def test_list_builds(config_from_file, next_page, capsys):
    response_data = json.loads(read_res('list_builds_response.json'))
    expected_output = read_res('list_builds_expected.txt')

    responses.add(
        responses.GET,
        'http://copr.fedoraproject.org/api_3/build/list',
        json=response_data, status=202)

    # no config
    config_from_file.side_effect = copr.v3.CoprNoConfigException("Dude, your config is missing")
    next_page.return_value = None

    main.main(argv=["list-builds", "praiskup/ping"])
    out, _ = capsys.readouterr()
    assert out.split("\n") == expected_output.split("\n")

@responses.activate
@mock.patch('copr_cli.main.config_from_file')
def test_list_packages(config_from_file, capsys):
    response_data = json.loads(read_res('list_packages_response.json'))
    expected_output = read_res('list_packages_expected.json')

    responses.add(
        responses.GET,
        'http://copr.fedoraproject.org/api_3/package/list',
        json=response_data, status=202)

    # no config
    config_from_file.side_effect = copr.v3.CoprNoConfigException("Dude, your config is missing")

    main.main(argv=["list-packages", "praiskup/ping"])
    out, _ = capsys.readouterr()
    assert json.loads(out) == json.loads(expected_output)

@responses.activate
@mock.patch('copr_cli.main.config_from_file')
def test_get_package(config_from_file, capsys):

    response_data = json.loads(read_res('get_package_response.json'))
    response_build_data = json.loads(read_res('get_package_response_builds.json'))
    expected_output = read_res('get_package_expected.json')

    responses.add(
        responses.GET,
        'http://copr.fedoraproject.org/api_3/package',
        json=response_data, status=202)

    responses.add(
        responses.GET,
        'http://copr.fedoraproject.org/api_3/build/list',
        json=response_build_data, status=202)


    # no config
    config_from_file.side_effect = copr.v3.CoprNoConfigException("Dude, your config is missing")

    main.main(argv=[
        "get-package", "--name", "binutils", "--with-all-builds",
        "praiskup/autoconf-2.71-attempts", "--with-latest-succeeded-build",
    ])
    out, _ = capsys.readouterr()
    assert json.loads(out) == json.loads(expected_output)

@mock.patch('copr_cli.main.config_from_file')
def test_list_project_no_username(config_from_file, capsys):
    config_from_file.side_effect = copr.v3.CoprNoConfigException()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["list"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()
    assert "Pass username to command or create `~/.config/copr`" in err


@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_list_project_no_username2(config_from_file, capsys):
    with pytest.raises(SystemExit) as err:
        main.main(argv=["list"])

    assert exit_wrap(err.value) == 6
    out, err = capsys.readouterr()
    assert "Pass username to command or add it to `~/.config/copr`" in err


@mock.patch('copr.v3.proxies.project.ProjectProxy.get_list')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_list_project_empty_list(config_from_file, get_list, capsys):
    get_list.return_value = []
    main.main(argv=["list", "projectname"])

    out, err = capsys.readouterr()
    assert "error" not in out
    assert "No copr retrieved for user: dummy"


@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_status_response(config_from_file, build_proxy_get, capsys):
    response_status = "foobar"
    build_proxy_get.return_value = MagicMock(state=response_status)

    main.main(argv=["status", "123"])
    out, err = capsys.readouterr()
    assert "{0}\n".format(response_status) in out


@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_debug_by_status_response(config_from_file, build_proxy_get, capsys):
    response_status = "foobar"
    build_proxy_get.return_value = MagicMock(state=response_status)

    main.main(argv=["--debug", "status", "123"])
    stdout, stderr = capsys.readouterr()
    assert "{0}\n".format(response_status) in stdout
    assert "Debug log enabled " in stderr


def test_status_response_no_args(capsys):
    with pytest.raises(SystemExit) as err:
        main.main(argv=["status"])

    assert exit_wrap(err.value) == 2

    stdout, stderr = capsys.readouterr()
    assert "usage: copr" in stderr


@mock.patch('copr.v3.proxies.project.ProjectProxy.delete')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_delete_project(config_from_file, project_proxy_delete, capsys):
    project_proxy_delete.return_value = Munch(name="foo")

    main.main(argv=["delete", "foo"])
    out, err = capsys.readouterr()
    assert out == "Project foo has been deleted.\n"


@mock.patch('copr_cli.main.subprocess')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr.v3.proxies.build_chroot.BuildChrootProxy.get_list')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_download_build(config_from_file, build_chroot_proxy_get_list, build_proxy_get, mock_sp, capsys):
    build_proxy_get.return_value = MagicMock(
        repo_url="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20")

    mock_ch1 = MagicMock()
    mock_ch1.configure_mock(
        name="epel-6-x86_64",
        result_url="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20")

    mock_ch2 = MagicMock()
    mock_ch2.configure_mock(
        name="epel-6-i386",
        result_url="http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20")
    build_chroot_proxy_get_list.return_value = [mock_ch1, mock_ch2]

    mock_sp.call.return_value = None
    main.main(argv=["download-build", "foo"])
    stdout, stderr = capsys.readouterr()

    expected_sp_call_args = [
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', '"index.html*"',
            '-e', 'robots=off', '--no-verbose', '-P', './epel-6-x86_64',
            '--cut-dirs', '6',
            'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20'
        ]),
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', '"index.html*"',
            '-e', 'robots=off', '--no-verbose', '-P', './epel-6-i386',
            '--cut-dirs', '6',
            'http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20'
        ])
    ]

    for call_args_list in mock_sp.call.call_args_list:
        assert call_args_list in expected_sp_call_args


@mock.patch('copr_cli.main.subprocess')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr.v3.proxies.build_chroot.BuildChrootProxy.get_list')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_download_build_select_chroot(config_from_file, build_chroot_proxy_get_list, build_proxy_get, mock_sp, capsys):
    build_proxy_get.return_value = MagicMock(
        repo_url="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20")

    mock_ch1 = MagicMock()
    mock_ch1.configure_mock(
        name="epel-6-x86_64",
        result_url="http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20")

    mock_ch2 = MagicMock()
    mock_ch2.configure_mock(
        name="epel-6-i386",
        result_url="http://example.com/results/epel-6-i386/python-copr-1.50-1.fc20")
    build_chroot_proxy_get_list.return_value = [mock_ch1, mock_ch2]

    mock_sp.call.return_value = None
    main.main(argv=["download-build", "foo", "-r", "epel-6-x86_64"])
    stdout, stderr = capsys.readouterr()
    expected_sp_call_args = [
        mock.call([
            'wget', '-r', '-nH', '--no-parent', '--reject', '"index.html*"',
            '-e', 'robots=off', '--no-verbose', '-P', u'./epel-6-x86_64',
            '--cut-dirs', '6',
            'http://example.com/results/epel-6-x86_64/python-copr-1.50-1.fc20'
        ]),
    ]

    assert mock_sp.call.call_args_list == expected_sp_call_args


@mock.patch('copr.v3.proxies.project.ProjectProxy.add')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_project(config_from_file, project_proxy_add, capsys):
    main.main(argv=[
        "create", "foo",
        "--chroot", "f20", "--chroot", "f21",
        "--description", "desc string",
        "--instructions", "instruction string",
        "--repo", "repo1", "--repo", "repo2",
        "--initial-pkgs", "pkg1"
    ])
    stdout, stderr = capsys.readouterr()

    project_proxy_add.assert_called_once()
    args, kwargs = project_proxy_add.call_args
    assert kwargs == {
        "auto_prune": True,
        "ownername": None, "persistent": False, "projectname": "foo", "description": "desc string",
        "instructions": "instruction string", "chroots": ["f20", "f21"],
        "additional_repos": ["repo1", "repo2"],
        "unlisted_on_hp": None, "devel_mode": None, "enable_net": False,
        "bootstrap": "default",
        'isolation': 'default',
        "delete_after_days": None,
        "multilib": False,
        "module_hotfixes": False,
        "fedora_review": False,
        "appstream": True,
    }
    assert stdout == "New project was successfully created.\n"


@mock.patch('copr.v3.proxies.project.ProjectProxy.add')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_project_with_isolation(_config_from_file, project_proxy_add, capsys):
    main.main(argv=[
        "create", "foo",
        "--chroot", "f20", "--chroot", "f21",
        "--isolation", "simple",
    ])
    stdout, stderr = capsys.readouterr()

    project_proxy_add.assert_called_once()
    kwargs = project_proxy_add.call_args[1]
    assert stderr == ''
    assert kwargs["isolation"] == "simple"
    assert stdout == "New project was successfully created.\n"


@mock.patch('copr.v3.proxies.project_chroot.ProjectChrootProxy.edit')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_edit_chroot_with_isolation(_config_from_file, project_chroot_proxy_edit, capsys):
    main.main(argv=[
        "edit-chroot", "foo/f20",
        "--isolation", "simple",
    ])
    stdout, stderr = capsys.readouterr()
    project_chroot_proxy_edit.assert_called_once()
    kwargs = project_chroot_proxy_edit.call_args[1]
    assert stderr == ''
    assert kwargs["isolation"] == "simple"
    assert stdout == "Edit chroot operation was successful.\n"


@mock.patch('copr.v3.proxies.project_chroot.ProjectChrootProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_get_chroot_output_format_json(_config_from_file, project_chroot_proxy_get, capsys):
    project_chroot_proxy_get.return_value = Munch(
        projectname="foo",
        additional_packages=[],
        additional_repos=[],
        comps_name="None",
        delete_after_days="None",
        isolation="None",
        mock_chroot="fedora-20-x86_64",
        ownername="None",
        with_opts=[],
        without_opts=[]
    )
    main.main(argv=[
        "get-chroot", "foo/f20",
    ])
    stdout, stderr = capsys.readouterr()
    project_chroot_proxy_get.assert_called_once()
    json_values = json.loads(stdout)
    assert stderr == ''
    assert json_values["projectname"] == "foo"
    assert json_values["mock_chroot"] == "fedora-20-x86_64"


@mock.patch('copr.v3.proxies.project.ProjectProxy.add')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_multilib_project(config_from_file, project_proxy_add, capsys):
    main.main(argv=[
        "create", "foo",
        '--multilib', 'on',
        "--chroot", "fedora-rawhide-x86_64",
        "--chroot", "fedora-rawhide-i386",
        "--instructions", "instruction string",
        "--repo", "repo1", "--repo", "repo2",
        "--initial-pkgs", "pkg1",
    ])
    stdout, stderr = capsys.readouterr()

    project_proxy_add.assert_called_once()
    args, kwargs = project_proxy_add.call_args
    assert kwargs == {
        "auto_prune": True,
        "ownername": None, "persistent": False, "projectname": "foo",
        "description": None,
        "instructions": "instruction string",
        "chroots": ["fedora-rawhide-x86_64", "fedora-rawhide-i386"],
        "additional_repos": ["repo1", "repo2"],
        "unlisted_on_hp": None, "devel_mode": None, "enable_net": False,
        'bootstrap': 'default',
        'isolation': 'default',
        "delete_after_days": None,
        "multilib": True,
        "module_hotfixes": False,
        "fedora_review": False,
        "appstream": True,
    }
    assert stdout == "New project was successfully created.\n"


@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
@mock.patch('copr_cli.main.Commands._watch_builds')
def test_create_build_no_wait_ok(watch_builds, config_from_file, create_from_url, auth_check, capsys):
    create_from_url.return_value = Munch(projectname="foo", id=123)

    main.main(argv=[
        "build", "--nowait",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert "Created builds" in stdout
    assert "Build was added to foo" in stdout
    assert not watch_builds.called


@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
@mock.patch('copr_cli.main.Commands._watch_builds')
def test_create_build_no_wait_error(watch_builds, config_from_file,create_from_url, autch_check, capsys):
    response_message = "foobar"
    create_from_url.side_effect = copr.v3.CoprRequestException(response_message)

    with pytest.raises(SystemExit) as err:
        main.main(argv=[
            "build", "--nowait",
            "copr_name", "http://example.com/pkgs.srpm"
        ])

    stdout, stderr = capsys.readouterr()
    assert response_message in stderr
    assert not watch_builds.called


@mock.patch('copr_cli.main.time')
@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_build_wait_succeeded_no_sleep(config_from_file, build_proxy_get,
                                              create_from_url, auth_check, mock_time, capsys):
    create_from_url.return_value = Munch(projectname="foo", id=123)
    build_proxy_get.return_value = Munch(state="succeeded")
    main.main(argv=[
        "build",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert "Created builds" in stdout
    assert "Watching build" in stdout
    assert not mock_time.sleep.called


@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_build_wait_error_status(config_from_file, build_proxy_get, create_from_url, auth_check, capsys):
    create_from_url.return_value = Munch(projectname="foo", id=123)
    build_proxy_get.side_effect = copr.v3.CoprRequestException()
    with pytest.raises(SystemExit) as err:
        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])
        assert exit_wrap(err.value) == 1

    stdout, stderr = capsys.readouterr()
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_build_wait_unknown_build_status(config_from_file, build_proxy_get, create_from_url, auth_check, capsys):
    create_from_url.return_value = Munch(projectname="foo", id=123)
    build_proxy_get.return_value = Munch(state="unknown")
    with pytest.raises(SystemExit) as err:
        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])
        assert exit_wrap(err.value) == 1

    stdout, stderr = capsys.readouterr()
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
@mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
@mock.patch('copr.v3.proxies.build.BuildProxy.get')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_create_build_wait_keyboard_interrupt(config_from_file, build_proxy_get, create_from_url, autch_check, capsys):
    create_from_url.return_value = Munch(projectname="foo", id=123)
    build_proxy_get.side_effect = KeyboardInterrupt

    main.main(argv=[
        "build",
        "copr_name", "http://example.com/pkgs.srpm"
    ])

    stdout, stderr = capsys.readouterr()
    assert "Created builds" in stdout
    assert "Watching build" in stdout


@mock.patch('copr_cli.main.time')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
class TestCreateBuild(object):

    @mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
    @mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
    @mock.patch('copr.v3.proxies.build.BuildProxy.get')
    def test_create_build_wait_succeeded_complex(self, build_proxy_get, create_from_url, auth_check,
                                                 config_from_file, mock_time, capsys):
        create_from_url.return_value = Munch(projectname="foo", id=1)
        self.stage = 0

        def incr(*args, **kwargs):
            self.stage += 1

        def result_map(*args, **kwargs):
            if self.stage == 0:
                return Munch(state="pending")
            elif self.stage == 1:
                smap = {0: "pending", 1: "starting", 2: "running"}
                return Munch(state=smap[kwargs["build_id"]])
            elif self.stage == 2:
                smap = {0: "starting", 1: "running", 2: "succeeded"}
                return Munch(state=smap[kwargs["build_id"]])
            elif self.stage == 3:
                smap = {0: "skipped", 1: "succeeded", 2: "succeeded"}
                return Munch(state=smap[kwargs["build_id"]])

        mock_time.sleep.side_effect = incr
        build_proxy_get.side_effect = result_map

        main.main(argv=[
            "build",
            "copr_name", "http://example.com/pkgs.srpm"
        ])

        stdout, stderr = capsys.readouterr()
        assert "Created builds" in stdout
        assert "Watching build" in stdout
        assert len(mock_time.sleep.call_args_list) == 3

    @mock.patch('copr.v3.proxies.BaseProxy.auth_check', return_value=True)
    @mock.patch('copr.v3.proxies.build.BuildProxy.create_from_url')
    @mock.patch('copr.v3.proxies.build.BuildProxy.get')
    def test_create_build_wait_failed_complex(self, build_proxy_get, create_from_url, auth_check,
                                              config_from_file, mock_time, capsys):
        create_from_url.return_value = Munch(projectname="foo", id=1)
        self.stage = 0

        def incr(*args, **kwargs):
            self.stage += 1

        def result_map(*args, **kwargs):
            if self.stage == 0:
                return Munch(state="pending")
            elif self.stage == 1:
                smap = {0: "pending", 1: "starting", 2: "running"}
                return Munch(state=smap[kwargs["build_id"]])
            elif self.stage == 2:
                smap = {0: "failed", 1: "running", 2: "succeeded"}
                return Munch(state=smap[kwargs["build_id"]])
            elif self.stage == 3:
                smap = {0: "failed", 1: "failed", 2: "succeeded"}
                return Munch(state=smap[kwargs["build_id"]])

        mock_time.sleep.side_effect = incr
        build_proxy_get.side_effect = result_map

        with pytest.raises(SystemExit) as err:
            main.main(argv=[
                "build",
                "copr_name", "http://example.com/pkgs.srpm"
            ])

        stdout, stderr = capsys.readouterr()
        assert "Created builds" in stdout
        assert "Watching build" in stdout
        assert "Build(s) 1 failed" in stderr
        assert len(mock_time.sleep.call_args_list) == 3

@mock.patch('copr_cli.main.Commands.action_permissions_edit',
            new_callable=MagicMock())
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_edit_permissions_output(_config, action):
    def test_me(args, expected_output):
        main.main(['edit-permissions'] + args)
        args = action.call_args[0][0]
        assert args.permissions == expected_output


    with pytest.raises(SystemExit) as err:
        main.main(['edit-permissions'])
    assert err.value.code == 2
    assert len(action.call_args_list) == 0

    test_me(['some/project'], None)
    test_me(
        ['some/project', '--admin', 'a', '--admin', 'b'],
        {'a': {'admin': 'approved'},
         'b': {'admin': 'approved'}}
    )
    test_me(
        ['some/project', '--admin', 'praiskup=nothing', '--admin', 'b'],
        {'b': {'admin': 'approved'},
         'praiskup': {'admin': 'nothing'}}
    )
    test_me(
        ['some/project', '--builder', 'praiskup', '--admin', 'praiskup'],
        {'praiskup': {'admin': 'approved', 'builder': 'approved'}}
    )

@mock.patch('copr_cli.main.Commands.action_permissions_request',
            new_callable=MagicMock())
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_edit_permissions_request(ocnfig, action):
    def test_me(args, expected_output):
        main.main(['request-permissions'] + args)
        args = action.call_args[0][0]
        assert args.permissions == expected_output

    with pytest.raises(SystemExit) as err:
        main.main(['request-permissions'])
    assert err.value.code == 2
    assert len(action.call_args_list) == 0

    test_me(['some/project'], None)

    with pytest.raises(SystemExit) as err:
        test_me(['some/project', '--admin', '--admin'], None)
    with pytest.raises(SystemExit) as err:
        test_me(['some/project', '--admin', '--admin', 'b'], None)
    assert err.value.code == 2

    test_me(
        ['some/project', '--admin', 'bad_status'],
        {'your user': {'admin': 'bad_status'}} )
    test_me(
        ['some/project', '--admin', '--builder'],
        {'your user': {'admin': 'request', 'builder': 'request'}})
    test_me( # we don't parse '=' here
        ['some/project', '--admin', 'bad_status=nothing'],
        {'your user': {'admin': 'bad_status=nothing'}} )


@mock.patch('copr.v3.proxies.mock_chroot.MockChrootProxy.get_list')
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_list_chroots(config, list_chroots):
    list_chroots.return_value = Munch({
        "fedora-18-x86_64": "",
        "fedora-17-x86_64": "A short chroot comment",
        "fedora-17-i386": "Chroot comment containing [url with four\nwords](https://copr.fedorainfracloud.org/)",
        "fedora-rawhide-i386": "",
    })

    main.main(argv=["list-chroots"])


@pytest.mark.parametrize('patch_name', ['build_from_file', 'build_from_url'])
@pytest.mark.parametrize('args', [[], ['--distgit', 'test']])
@mock.patch('copr_cli.main.config_from_file', return_value=mock_config)
def test_module_build(config, patch_name, args):
    argv = ["build-module", "testproject"]

    if patch_name == 'build_from_file':
        argv += ["--yaml", "non-existing.yaml"]
    else:
        argv += ["--url", "http://example.com/test.yml"]

    module = 'copr.v3.proxies.module'
    with mock.patch('{0}.ModuleProxy.{1}'.format(module, patch_name)) as p:
        main.main(argv=argv + args)

        assert len(p.call_args_list) == 1
        kwargs = p.call_args_list[0][1]
        assert 'distgit' in kwargs
        if args:
            assert kwargs['distgit'] == args[1]
        else:
            assert kwargs['distgit'] is None
