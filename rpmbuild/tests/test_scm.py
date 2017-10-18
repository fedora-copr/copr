import mock
import unittest
import tempfile
import os
import configparser
from ..copr_rpmbuild.providers.scm import ScmProvider
from ..copr_rpmbuild.helpers import read_config

from mock import patch, MagicMock

CONFIG = """
[main]
frontend_url = https://copr.fedoraproject.org
resultdir = /var/lib/copr-rpmbuild/results

[distgit0]
distgit_hostname_pattern = src.fedoraproject.org
distgit_lookaside_url = https://src.fedoraproject.org/repo/pkgs
distgit_clone_url = https://src.fedoraproject.org

[distgit1]
distgit_hostname_pattern = copr-dist-git.fedorainfracloud.org
distgit_lookaside_url = http://copr-dist-git.fedorainfracloud.org/repo/pkgs
distgit_clone_url = http://copr-dist-git.fedorainfracloud.org/git

[distgit2]
distgit_hostname_pattern = pkgs.fedoraproject.org
distgit_lookaside_url = https://src.fedoraproject.org/repo/pkgs
distgit_clone_url = git://pkgs.fedoraproject.org
"""

RPKG_CONF_JINJA = """
[rpkg]
lookaside = {{ lookaside_url }}
anongiturl = {{ clone_url }}/%(module)s
"""

class TestScmProvider(unittest.TestCase):
    def setUp(self):
        self.source_json = {
            "type": "git",
            "clone_url": "https://example.org/somerepo.git",
            "committish": "f28",
            "subdirectory": "subpkg",
            "spec": "pkg.spec",
            "srpm_build_method": "rpkg",
        }
        self.resultdir = "/path/to/resultdir"
        fd, config_path = tempfile.mkstemp()
        f = open(fd, 'w')
        f.write(CONFIG)
        f.close()
        self.config = read_config(config_path)

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

        with patch("rpmbuild.copr_rpmbuild.providers.scm.CONF_DIRS", new=[rpkg_tmpdir]):
            provider = ScmProvider(source_json, self.resultdir, self.config)
            rpkg_config_path = provider.generate_rpkg_config()

        config = configparser.RawConfigParser()
        config.read(rpkg_config_path)
        self.assertTrue(config.has_section("rpkg"))
        self.assertEqual(config.get("rpkg", "lookaside"), "http://copr-dist-git.fedorainfracloud.org/repo/pkgs")
        self.assertEqual(config.get("rpkg", "anongiturl"),  "http://copr-dist-git.fedorainfracloud.org/git/%(module)s")

        source_json["clone_url"] = "http://unknownurl/git/clime/project/pkg.git"

        with patch("rpmbuild.copr_rpmbuild.providers.scm.CONF_DIRS", new=[rpkg_tmpdir]):
            provider = ScmProvider(source_json, self.resultdir, self.config)
            rpkg_config_path = provider.generate_rpkg_config()
            self.assertEqual(rpkg_config_path, "/etc/rpkg.conf")

    def test_get_rpkg_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        provider.generate_rpkg_config = MagicMock(return_value="/etc/rpkg.conf")
        assert_cmd = ["rpkg", "-C", "/etc/rpkg.conf", "srpm",
                      "--outdir", self.resultdir, "--spec", provider.spec_path]
        self.assertEqual(provider.get_rpkg_command(), assert_cmd)

    def test_get_tito_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        assert_cmd = ["tito", "build", "--srpm", "--output", self.resultdir]
        self.assertEqual(provider.get_tito_command(), assert_cmd)

    def test_get_tito_test_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        assert_cmd = ["tito", "build", "--test", "--srpm", "--output", self.resultdir]
        self.assertEqual(provider.get_tito_test_command(), assert_cmd)

    def test_get_make_srpm_command(self):
        provider = ScmProvider(self.source_json, self.resultdir, self.config)
        bind_mount_cmd_part = '--plugin-option=bind_mount:dirs=(("{0}", "/mnt{1}"), ("{2}", "/mnt{3}"))'\
                              .format(provider.workdir, provider.workdir, self.resultdir, self.resultdir)
        make_srpm_cmd_part = 'cd /mnt{0}/somerepo/subpkg; make -f /mnt{1}/somerepo/.copr/Makefile srpm '\
                             'outdir="/mnt{2}" spec="/mnt{3}/somerepo/subpkg/pkg.spec"'\
                             .format(provider.workdir, provider.workdir, self.resultdir, provider.workdir)
        assert_cmd = ['mock', '-r', '/etc/copr-rpmbuild/make_srpm_mock.cfg',
                      bind_mount_cmd_part, '--chroot', make_srpm_cmd_part]

        self.assertEqual(provider.get_make_srpm_command(), assert_cmd)
