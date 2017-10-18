import re
import unittest
import mock
import configparser
from os.path import realpath, dirname
from ..copr_rpmbuild.builders.mock import MockBuilder
import subprocess
import datetime

from unittest.mock import MagicMock

class TestMockBuilder(unittest.TestCase):
    def setUp(self):
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
            "use_bootstrap_container": False,
        }
        self.sourcedir = "/path/to/sourcedir"
        self.resultdir = "/path/to/resultdir"
        self.config = configparser.RawConfigParser()
        self.config.add_section('main')
        self.config.set('main', 'logfile', '/path/to/logfile')

    def test_init(self):
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        self.assertEqual(builder.task_id, "10-fedora-24-x86_64")
        self.assertEqual(builder.chroot, "fedora-24-x86_64")
        self.assertEqual(builder.buildroot_pkgs, ["pkg1", "pkg2", "pkg3"])
        self.assertEqual(builder.enable_net, True)
        self.assertEqual(builder.repos, [])
        self.assertEqual(builder.use_bootstrap_container, False)

    def test_render_config_template(self):
        confdirs = [dirname(dirname(realpath(__file__)))]
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        cfg = builder.render_config_template()

        # Parse the rendered config
        # This is how mock itself does it
        def include(*args, **kwargs):
            pass
        config_opts = {"yum.conf": []}
        cfg = re.sub(r'include\((.*)\)', r'include(\g<1>, config_opts, True)', cfg)
        code = compile(cfg, "/tmp/foobar", 'exec')
        exec(code)

        self.assertEqual(config_opts["root"], "10-fedora-24-x86_64")
        self.assertEqual(config_opts["chroot_additional_packages"], "pkg1 pkg2 pkg3")
        self.assertEqual(config_opts["rpmbuild_networking"], True)
        self.assertEqual(config_opts["use_bootstrap_container"], False)
        self.assertEqual(config_opts["yum.conf"], [])

    @mock.patch("rpmbuild.copr_rpmbuild.builders.mock.subprocess.Popen")
    def test_produce_rpm(self, popen_mock):
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        builder.get_mock_uniqueext = MagicMock(return_value='2')
        process = MagicMock(returncode=0)
        popen_mock.return_value = process
        builder.produce_rpm("/path/to/pkg.src.rpm", "/path/to/configs", "/path/to/results")
        assert_cmd = ['unbuffer', '/usr/bin/mock',
                      '--rebuild', '/path/to/pkg.src.rpm',
                      '--configdir', '/path/to/configs',
                      '--resultdir', '/path/to/results',
                      '--uniqueext', '2',
                      '-r', 'child']
        popen_mock.assert_called_with(assert_cmd, stdin=subprocess.PIPE, preexec_fn=builder.preexec_fn_build_stream)

    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_touch_success_file(self, mock_open):
        builder = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        builder.touch_success_file()
        mock_open.assert_called_with("/path/to/resultdir/success", "w")

    def test_custom1_chroot_settings(self):
        b1 = MockBuilder(self.task, self.sourcedir, self.resultdir, self.config)
        b2 = MockBuilder(dict(self.task, **{"chroot": "custom-1-x86_64"}), self.sourcedir, self.resultdir, self.config)
        self.assertEqual(b1.pkg_manager_conf, "yum")
        self.assertEqual(b2.pkg_manager_conf, "dnf")
