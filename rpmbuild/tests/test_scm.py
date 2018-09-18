import tempfile
import os
import configparser
import shutil

from copr_rpmbuild.providers.scm import ScmProvider
from copr_rpmbuild.helpers import read_config
from . import TestCase

try:
     from unittest import mock
except ImportError:
     # Python 2 version depends on mock
     import mock

RPKG_CONF_JINJA = """
[rpkg]
lookaside = {{ lookaside_url }}
anongiturl = {{ clone_url }}/%(module)s
"""

class TestScmProvider(TestCase):
    def setUp(self):
        super(TestScmProvider, self).setUp()
        self.source_json = {
            "type": "git",
            "clone_url": "https://example.org/somerepo.git",
            "committish": "f28",
            "subdirectory": "subpkg",
            "spec": "pkg.spec",
            "srpm_build_method": "rpkg",
        }
        self.resultdir = "/path/to/resultdir"

    def test_init(self):
        source_json = self.source_json.copy()

        provider = ScmProvider(source_json, self.resultdir, self.config)
        self.assertEqual(provider.scm_type, "git")
        self.assertEqual(provider.clone_url, "https://example.org/somerepo.git")
        self.assertEqual(provider.committish, "f28")
        self.assertEqual(provider.repo_subdir, "subpkg")
        self.assertEqual(provider.spec_relpath, "pkg.spec")
        self.assertEqual(provider.srpm_build_method, "rpkg")
        self.assertEqual(provider.repo_dirname, "somerepo")
        self.assertEqual(provider.repo_path, os.path.join(provider.workdir, "somerepo"))
        self.assertEqual(provider.repo_subpath, os.path.join(provider.workdir, "somerepo", "subpkg"))
        self.assertEqual(provider.spec_path, os.path.join(provider.workdir, "somerepo", "subpkg", "pkg.spec"))

        source_json["subdirectory"] = "/SOURCES"
        source_json["spec"] = "/SPECS/pkg.spec"
        provider = ScmProvider(source_json, self.resultdir, self.config)
        self.assertEqual(provider.repo_subdir, "/SOURCES")
        self.assertEqual(provider.spec_relpath, "/SPECS/pkg.spec")
        self.assertEqual(provider.repo_path, os.path.join(provider.workdir, "somerepo"))
        self.assertEqual(provider.repo_subpath, os.path.join(provider.workdir, "somerepo", "SOURCES"))
        self.assertEqual(provider.spec_path, os.path.join(provider.workdir, "somerepo", "SPECS", "pkg.spec"))

    def test_generate_rpkg_config(self):
        rpkg_tmpdir = tempfile.mkdtemp()
        rpkg_config = open(os.path.join(rpkg_tmpdir, "rpkg.conf.j2"), "w")
        rpkg_config.write(RPKG_CONF_JINJA)
        rpkg_config.close()

        source_json = self.source_json.copy()
        source_json["clone_url"] = "http://copr-dist-git.fedorainfracloud.org/git/clime/project/pkg.git"

        with mock.patch("copr_rpmbuild.providers.scm.CONF_DIRS", new=[rpkg_tmpdir]):
            provider = ScmProvider(source_json, self.resultdir, self.config)
            rpkg_config_path = provider.generate_rpkg_config()

        config = configparser.RawConfigParser()
        config.read(rpkg_config_path)
        self.assertTrue(config.has_section("rpkg"))
        self.assertEqual(config.get("rpkg", "lookaside"), "http://copr-dist-git.fedorainfracloud.org/repo/pkgs")
        self.assertEqual(config.get("rpkg", "anongiturl"),  "http://copr-dist-git.fedorainfracloud.org/git/%(module)s")

        source_json["clone_url"] = "http://unknownurl/git/clime/project/pkg.git"

        with mock.patch("copr_rpmbuild.providers.scm.CONF_DIRS", new=[rpkg_tmpdir]):
            provider = ScmProvider(source_json, self.resultdir, self.config)
            rpkg_config_path = provider.generate_rpkg_config()
            self.assertEqual(rpkg_config_path, os.path.join(os.environ['HOME'], '.config', 'rpkg.conf'))

        shutil.rmtree(rpkg_tmpdir)

    def test_get_rpkg_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        provider.generate_rpkg_config = mock.MagicMock(return_value="/etc/rpkg.conf")
        assert_cmd = ["rpkg", "srpm", "--outdir", self.resultdir, "--spec", provider.spec_path]
        self.assertEqual(provider.get_rpkg_command(), assert_cmd)

    def test_get_tito_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        assert_cmd = ["tito", "build", "--srpm", "--output", self.resultdir]
        self.assertEqual(provider.get_tito_command(), assert_cmd)


    @mock.patch("copr_rpmbuild.helpers.run_cmd")
    def test_get_tito_test_command(self, run_cmd_mock):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        assert_cmd = ["tito", "build", "--test", "--srpm", "--output", self.resultdir]
        self.assertEqual(provider.get_tito_test_command(), assert_cmd)

    @mock.patch("copr_rpmbuild.providers.scm.get_mock_uniqueext")
    def test_get_make_srpm_command(self, get_mock_uniqueext_mock):
        get_mock_uniqueext_mock.return_value = '2'
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        bind_mount_cmd_part = '--plugin-option=bind_mount:dirs=(("{0}", "/mnt{1}"), ("{2}", "/mnt{3}"))'\
                              .format(provider.workdir, provider.workdir, self.resultdir, self.resultdir)
        make_srpm_cmd_part = 'cd /mnt{0}/somerepo/subpkg; make -f /mnt{1}/somerepo/.copr/Makefile srpm '\
                             'outdir="/mnt{2}" spec="/mnt{3}/somerepo/subpkg/pkg.spec"'\
                             .format(provider.workdir, provider.workdir, self.resultdir, provider.workdir)
        assert_cmd = ['mock', '--uniqueext', '2', '-r', '/etc/copr-rpmbuild/make_srpm_mock.cfg',
                      bind_mount_cmd_part, '--chroot', make_srpm_cmd_part]

        self.assertEqual(provider.get_make_srpm_command(), assert_cmd)
