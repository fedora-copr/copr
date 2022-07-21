import re
import configparser
import os
import pytest
import shutil
import subprocess
import tempfile
from os.path import realpath, dirname

from copr_rpmbuild.builders.mock import MockBuilder

try:
     from unittest import mock
     builtins = 'builtins'
except ImportError:
     # Python 2 version depends on mock
     import mock
     builtins = '__builtin__'

@pytest.yield_fixture
def f_mock_calls():
    p_popen = mock.patch('copr_rpmbuild.builders.mock.GentlyTimeoutedPopen')

    dummy_patchers = [
        mock.patch('copr_rpmbuild.builders.mock.MockBuilder.mock_clean'),
        mock.patch('copr_rpmbuild.builders.mock.shutil'),
        mock.patch('copr_rpmbuild.builders.mock.locate_spec',
                   new=mock.MagicMock(return_value='spec')),
        mock.patch('copr_rpmbuild.builders.mock.locate_srpm',
                   new=mock.MagicMock(return_value='srpm')),
        mock.patch('copr_rpmbuild.builders.mock.get_mock_uniqueext',
                   new=mock.MagicMock(return_value='0')),
    ]

    for patcher in dummy_patchers:
        patcher.start()

    yield_val = p_popen.start()
    yield_val.return_value = mock.MagicMock(returncode=0)

    yield yield_val.call_args_list

    for patcher in dummy_patchers:
        patcher.stop()


class TestMockBuilder(object):
    def setup_method(self, method):
        self.task = {
            "_description": "dist-git build",
            "_expected_outcome": "success",

            "build_id": 10,
            "buildroot_pkgs": ["pkg1", "pkg2", "pkg3"],
            "chroot": "fedora-24-x86_64",
            "enable_net": True,
            "source_json": {
                "clone_url": "https://src.fedoraproject.org/git/rpms/389-admin-console.git",
                "branch": "f25",
            },
            "source_type": 7,
            "memory_reqs": 2048,
            "package_name": "example",
            "package_version": "1.0.5-1.git.0.78e06da.fc23",
            "pkgs": "",
            "project_name": "copr-dev",
            "project_owner": "@copr",
            "repos": [],
            "submitter": "clime",
            "task_id": "10-fedora-24-x86_64",
            "timeout": 21600,
            "with_opts": [],
            "without_opts": [],
            "isolation": "default",
        }

        self.sourcedir = "/path/to/sourcedir"
        self.resultdir = tempfile.mkdtemp(prefix='test-mock-builder')
        self.configdir = os.path.join(self.resultdir, 'configs')
        self.child_config = os.path.join(self.configdir, 'child.cfg')

        self.mock_rpm_call = [
            'unbuffer', 'mock', '--rebuild', 'srpm',
            '--resultdir', self.resultdir, '--uniqueext', '0',
            '-r', self.child_config,
        ]

        self.mock_srpm_call = [
            'unbuffer', 'mock', '--buildsrpm', '--spec', 'spec', '--sources',
            self.sourcedir, '--resultdir', self.resultdir, '--uniqueext', '0',
            '-r', self.child_config]

        self.config = configparser.RawConfigParser()
        self.config.add_section('main')
        self.config.set('main', 'logfile', '/dev/null')
        self.config.set('main', 'rpm_vendor_copr_name', 'Copr Testsuite')

    def teardown_method(self, method):
        shutil.rmtree(self.resultdir)

    def test_init(self):
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        assert builder.task_id == "10-fedora-24-x86_64"
        assert builder.chroot == "fedora-24-x86_64"
        assert builder.buildroot_pkgs == ["pkg1", "pkg2", "pkg3"]
        assert builder.enable_net
        assert builder.repos == []
        assert not builder.bootstrap
        assert not builder.bootstrap_image

    def test_render_config_template(self):
        confdirs = [dirname(dirname(realpath(__file__)))]
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        cfg = builder.render_config_template()

        # Parse the rendered config
        # This is how mock itself does it
        def include(*args, **kwargs):
            pass

        config_opts = {"macros": {"%copr_username": "@copr", "%copr_projectname": "copr-dev"}, "yum.conf": []}
        cfg = re.sub(r'include\((.*)\)', r'include(\g<1>, config_opts, True)', cfg)
        code = compile(cfg, "/tmp/foobar", 'exec')
        exec(code)

        assert config_opts["chroot_additional_packages"] == "pkg1 pkg2 pkg3"
        assert config_opts["rpmbuild_networking"]
        assert "use_bootstrap" not in config_opts
        assert "bootstrap" not in config_opts
        assert "bootstrap_image" not in config_opts
        assert "isolation" not in config_opts
        assert config_opts["macros"]["%copr_username"] == "@copr"
        assert config_opts["macros"]["%copr_projectname"] == "copr-dev"
        assert config_opts["yum.conf"] == []

    @mock.patch("copr_rpmbuild.builders.mock.subprocess.call")
    def test_mock_config(self, call, f_mock_calls):
        """ test that no module_enable statements are in config """
        self.task["isolation"] = "nspawn"
        MockBuilder(self.task, self.sourcedir, self.resultdir,
                    self.config).run()

        config = open(self.child_config, 'r').readlines()
        config = ''.join(config)
        assert config == """\
include('/etc/mock/fedora-24-x86_64.cfg')

config_opts.setdefault('plugin_conf', {})
config_opts['plugin_conf'].setdefault('tmpfs_opts', {})
config_opts['plugin_conf']['tmpfs_opts']['keep_mounted'] = True


config_opts['chroot_additional_packages'] = 'pkg1 pkg2 pkg3'


config_opts['rpmbuild_networking'] = True
config_opts['use_host_resolv'] = True

config_opts['isolation'] = 'nspawn'
config_opts['macros']['%copr_username'] = '@copr'
config_opts['macros']['%copr_projectname'] = 'copr-dev'
config_opts['macros']['%vendor'] = 'Copr Testsuite - group @copr'
config_opts['macros']['%buildtag'] = '.copr10'
config_opts['macros']['%dist'] = '%nil'
config_opts['macros']['%_disable_source_fetch'] = '0'

"""  # TODO: make the output nicer

    @mock.patch("copr_rpmbuild.builders.mock.MockBuilder.prepare_configs")
    @mock.patch("copr_rpmbuild.builders.mock.MockBuilder.archive_configs")
    def test_mock_options(self, archive_configs, prep_configs, f_mock_calls):
        """ test that mock options are correctly constructed """
        MockBuilder(self.task, self.sourcedir, self.resultdir,
                    self.config).run()
        assert len(f_mock_calls) == 2 # srpm + rpm

        call = f_mock_calls[0]
        assert call[0][0] == self.mock_srpm_call

        call = f_mock_calls[1]
        assert call[0][0] == self.mock_rpm_call

    @mock.patch("copr_rpmbuild.builders.mock.subprocess.call")
    @mock.patch("copr_rpmbuild.builders.mock.MockBuilder.prepare_configs")
    @mock.patch("copr_rpmbuild.builders.mock.get_mock_uniqueext")
    @mock.patch("copr_rpmbuild.builders.mock.GentlyTimeoutedPopen")
    def test_produce_rpm(self, popen_mock, get_mock_uniqueext_mock,
                         prep_configs, sp_call):
        get_mock_uniqueext_mock.side_effect = ['2', 'not_called_twice']
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        process = mock.MagicMock(returncode=0)
        popen_mock.return_value = process
        builder.produce_rpm("/path/to/pkg.src.rpm", "/path/to/results")
        assert_cmd = ['unbuffer', 'mock',
                      '--rebuild', '/path/to/pkg.src.rpm',
                      '--resultdir', '/path/to/results',
                      '--uniqueext', '2',
                      '-r', builder.mock_config_file]
        popen_mock.assert_called_with(assert_cmd, stdin=subprocess.PIPE,
                                      timeout=21600)
        builder.mock_clean()
        sp_call.assert_called_with(
            ['unbuffer', 'mock', '-r', builder.mock_config_file,
             '--uniqueext', '2', '--scrub', 'bootstrap', '--scrub', 'chroot',
             '--scrub', 'root-cache', '--quiet'])
        assert get_mock_uniqueext_mock.call_count == 1

    @mock.patch('{0}.open'.format(builtins), new_callable=mock.mock_open())
    def test_touch_success_file(self, mock_open):
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        builder.touch_success_file()
        success = os.path.join(self.resultdir, "success")
        mock_open.assert_called_with(success, "w")

    @pytest.mark.parametrize('modules', [
        ['postgresql:9.6'],
        ['moduleA:S1', 'moduleA:S2'],
        # we trim spaces around modules
        [' moduleA:S1', ' moduleA:S2 '],
    ])
    def test_module_mock_options(self, f_mock_calls, modules):
        'test that mock options for module-enable is correctly constructed'
        self.task['modules'] = {
            'toggle': [{'enable': x} for x in modules],
        }

        with mock.patch("copr_rpmbuild.builders.mock.subprocess.call"):
            MockBuilder(self.task, self.sourcedir, self.resultdir,
                        self.config).run()

        assert len(f_mock_calls) == 2 # srpm + rpm

        # srpm call isn't affected by modules
        call = f_mock_calls[0]
        assert call[0][0] == self.mock_srpm_call

        call = f_mock_calls[1]
        assert call[0][0] == self.mock_rpm_call

        expected1 = "config_opts['macros']['%buildtag'] = '.copr10'\n"
        expected2 = ("config_opts['module_setup_commands'] = {0}\n\n"
                     .format(str([('enable', module) for module in modules])))

        config = ''.join(open(self.child_config, 'r').readlines())
        assert expected1 in config
        assert expected2 in config

    @pytest.mark.parametrize('modules', [
        [], # dict expected
        "asf",
        {}, # toggle required for now
        {'toggle': []}, # can not be empty
        {'toggle': ""}, # string required
        {'toggle': [{'enable': 1}]}, # enable accepts string
    ])
    def test_module_mock_assertions(self, f_mock_calls, modules):
        'test that assertions work'
        self.task['modules'] = modules
        with mock.patch("copr_rpmbuild.builders.mock.subprocess.call"):
            with pytest.raises(AssertionError):
                MockBuilder(self.task, self.sourcedir, self.resultdir,
                            self.config).run()
