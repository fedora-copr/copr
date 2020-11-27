"""
Unit tests for the `copr mock-config ...` command.
"""

from munch import Munch
import pytest

from copr_cli import main

import six

from cli_tests_lib import mock, f_test_config


class TestMockConfig():
    j_prolog = """\
# This is development/testing only mock profile, not exactly the same as
# is used on copr builders;  but it is basically similar.  If you need an
# exact mock configuration (because you e.g. try to reproduce failed
# build), such configuration is put alongside the built RPMs.

"""

    @classmethod
    def j_repos(cls, priority=None, additional=None):
        priority = "priority={0}\n".format(priority) if priority else ""
        if additional:
            additional = '\n'.join([
                '\n[{id}]',
                'name="{name}"',
                'baseurl={url}',
                'gpgcheck=0',
                'enabled=1',
                'skip_if_unavailable=1',
                'metadata_expire=0',
                'cost=1',
                'best=1\n',
            ]).format(
                id=additional['id'],
                name=additional['name'],
                url=additional['baseurl']
            )
        else:
            additional=""

        return """
config_opts[config_opts['package_manager'] + '.conf'] += \"\"\"

[copr_base]
name="Copr repository"
baseurl=https://copr-be-dev.cloud.fedoraproject.org/results/praiskup/ping/fedora-rawhide-x86_64/
{0}gpgcheck=0
enabled=1
skip_if_unavailable=1
metadata_expire=0
cost=1
best=1
{1}\"\"\"
""".format(priority, additional)

    def get_build_config_result(self):
        return Munch({
            "additional_packages": [],
            # We have a bug in frontend code, because it mentions the copr_base
            # in this dict twice, once in additional_repos and once in repos.
            "additional_repos": ["copr://praiskup/ping"],
            "chroot": "fedora-rawhide-x86_64",
            "enable_net": False,
            "repos": [{
                "baseurl": "https://copr-be-dev.cloud.fedoraproject.org/results/praiskup/ping/fedora-rawhide-x86_64/",
                "id": "copr_base",
                "name": "Copr repository"
            }],
            "use_bootstrap_container": False,
            "with_opts": [],
            "without_opts":[],
            "isolation": "default"
        })

    @pytest.yield_fixture
    def f_get_build_config(self):
        method = (
            'copr.v3.proxies.project_chroot.'
            'ProjectChrootProxy.get_build_config'
        )
        with mock.patch(method) as patched:
            yield patched

    def main(self, args, capsys):
        main.main(['mock-config'] + args)
        return capsys.readouterr()

    def assert_output(self, capsys, args, exp_stdout, exp_stderr):
        stdout, stderr = self.main(args, capsys)
        assert self.j_prolog + exp_stdout == stdout
        assert exp_stderr == stderr

    def test_basic_repo(self, f_get_build_config, capsys, f_test_config):
        f_get_build_config.return_value = self.get_build_config_result()

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n"
            + self.j_repos(),
            "")

    def test_additional_package(self, f_get_build_config, f_test_config,
                                capsys):
        config = self.get_build_config_result()
        config.additional_packages = ['x']
        f_get_build_config.return_value = config

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n"
            "config_opts['chroot_additional_packages'] = 'x'\n"
            + self.j_repos(),
            "")

    def test_additional_packages(self, f_get_build_config, f_test_config,
                                 capsys):
        config = self.get_build_config_result()
        config.additional_packages = ['x', 'y', 'z']
        f_get_build_config.return_value = config

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n"
            "config_opts['chroot_additional_packages'] = 'x y z'\n"
            + self.j_repos(),
            "")

    def test_priority(self, f_get_build_config, f_test_config, capsys):
        config = self.get_build_config_result()
        config.repos[0]['priority'] = 99
        f_get_build_config.return_value = config

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n"
            + self.j_repos(priority=99),
            "")

    def test_no_repos(self, f_get_build_config, f_test_config, capsys):
        config = self.get_build_config_result()
        config.repos = []
        f_get_build_config.return_value = config

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n",
            "")

    def test_no_repos_with_additional(self, f_get_build_config, f_test_config, capsys):
        config = self.get_build_config_result()
        additional = {
            'id': 'x',
            'name': 'namex',
            'baseurl': 'http://xxx.org/',
        }
        config.repos.append(additional)
        f_get_build_config.return_value = config

        self.assert_output(
            capsys,
            ['test/test', 'fedora-rawhide-x86_64'],
            "include('/etc/mock/fedora-rawhide-x86_64.cfg')\n\n"
            "config_opts['root'] = 'test-test_fedora-rawhide-x86_64'\n"
            + self.j_repos(additional=additional),
            "")
