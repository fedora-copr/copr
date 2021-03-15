"""
Unit tests for the building/defining packages with DistGit method
"""

import copy

from munch import Munch
import pytest

import copr
from copr_cli import main
from cli_tests_lib import mock

# pylint: disable=unused-import
from cli_tests_lib import f_test_config

def _main(args, capsys):
    main.main(args)
    return capsys.readouterr()

def _assert_output(args, exp_stdout, exp_stderr, capsys):
    stdout, stderr = _main(args, capsys)
    assert exp_stdout == stdout
    assert exp_stderr == stderr

# pylint: disable=redefined-outer-name,unused-argument,missing-function-docstring

class TestDistGitMethodBuild(object):
    'Build was added to project:...uild/1\nCreated builds: 1\n'
    build_1 = (
        "Build was added to project:\n"
        "  http://copr/coprs/build/1\n"
        "Created builds: 1\n"
    )
    default_build_call = {
        'ownername': None,
        'projectname': 'project',
        'project_dirname': 'project',
        'buildopts': {
            'timeout': None,
            'chroots': None,
            'background': False,
            'progress_callback': None,
            'isolation': 'unchanged',
        },
        'packagename': 'test',
        'distgit': None,
        'namespace': None,
        'committish': None
    }

    @staticmethod
    @pytest.yield_fixture
    def f_patch_create_from_distgit(f_test_config, capsys):
        with mock.patch("copr.v3.proxies.build.BuildProxy.create_from_distgit") as patch:
            patch.return_value = [Munch({
                "id": "1",
                "projectname": "project",
            })]
            yield patch

    def test_normal_distgit_build(self, f_patch_create_from_distgit, capsys):
        _assert_output(
            ['build-distgit', '--name', 'test', 'project', '--nowait'],
            self.build_1, "",
            capsys)
        assert len(f_patch_create_from_distgit.call_args_list) == 1
        call = f_patch_create_from_distgit.call_args_list[0]
        assert call[1] == self.default_build_call

    @pytest.mark.parametrize('enable_net', ["on", "off"])
    def test_full_featured_distgit_build(self, enable_net,
                                         f_patch_create_from_distgit, capsys):
        _assert_output(
            ['build-distgit', '--name', 'test', '@group/project', '--nowait',
             '--timeout', "3600", '--chroot', 'fedora-rawhide-x86_64',
             '--distgit', 'centos', '--commit', 'f19', '--namespace',
             'rpms', "--background", "--enable-net", enable_net],
            self.build_1, "",
            capsys)
        assert len(f_patch_create_from_distgit.call_args_list) == 1
        call = f_patch_create_from_distgit.call_args_list[0]
        result = copy.deepcopy(self.default_build_call)
        result.update({
            "ownername": "@group",
            "committish": "f19",
            "distgit": "centos",
            "namespace": "rpms",
            "buildopts": {
                "timeout": "3600",
                "chroots": ['fedora-rawhide-x86_64'],
                "background": True,
                "progress_callback": None,
                'isolation': 'unchanged',
                "enable_net": enable_net == "on",
            },
        })
        assert call[1] == result


class TestDistGitMethodPackage(object):
    success_stdout = "Create or edit operation was successful.\n"

    @staticmethod
    @pytest.yield_fixture
    def f_patch_package_distgit(f_test_config, capsys):
        with mock.patch("copr.v3.proxies.package.PackageProxy.add") as p1:
            with mock.patch("copr.v3.proxies.package.PackageProxy.edit") as p2:
                yield p1, p2

    def test_add_package_normal(self, f_patch_package_distgit, capsys, ):
        _assert_output(['add-package-distgit', '--name', 'package',
                        'project'], self.success_stdout, "", capsys)
        assert len(f_patch_package_distgit[0].call_args_list) == 1
        assert len(f_patch_package_distgit[1].call_args_list) == 0

        call = f_patch_package_distgit[0].call_args_list[0]
        assert call == mock.call(
            None, "project", "package", "distgit",
            {'distgit': None,
             'namespace': None,
             'committish': None,
             'max_builds': None,
             'webhook_rebuild': None})

    def test_edit_package_full(self, f_patch_package_distgit, capsys):
        _assert_output(['edit-package-distgit', '--name', 'package', '@owner/project',
                        '--commit', 'master', '--namespace', 'ns', '--distgit',
                        'centos', '--webhook-rebuild', "on", "--max-builds",
                        "1"],
                       self.success_stdout, "", capsys)
        assert len(f_patch_package_distgit[1].call_args_list) == 1
        assert len(f_patch_package_distgit[0].call_args_list) == 0

        call = f_patch_package_distgit[1].call_args_list[0]
        assert call == mock.call(
            "@owner", "project", "package", "distgit",
            {'distgit': "centos",
             'namespace': "ns",
             'committish': "master",
             'max_builds': "1",
             'webhook_rebuild': True})

    @staticmethod
    def test_edit_package_fail(f_test_config, capsys):
        with mock.patch("copr.v3.proxies.package.PackageProxy.add") as p1:
            p1.side_effect = copr.v3.CoprRequestException("test")
            with pytest.raises(SystemExit) as exc:
                main.main(['edit-package-distgit', '--name', 'package',
                           '@owner/project/blah'])
            assert exc.value.code == 1

        out, err = capsys.readouterr()
        assert out == ""
        assert err == (
            "\nSomething went wrong:\n"
            "Error: Unable to connect to http://copr/api_3/.\n"
        )
