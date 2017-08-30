import unittest
import mock
import ConfigParser
import StringIO
from ..main import DistGitProvider


class TestDistGitProvider(unittest.TestCase):
    def setUp(self):
        self.source_json = {"clone_url": "https://src.fedoraproject.org/git/rpms/389-admin-console.git",
                            "branch": "f25"}
        self.empty_source_json = {"clone_url": None, "branch": None}

    def test_init(self):
        provider = DistGitProvider(self.source_json)
        self.assertEqual(provider.clone_url, "https://src.fedoraproject.org/git/rpms/389-admin-console.git")
        self.assertEqual(provider.branch, "f25")

    @mock.patch("rpmbuild.main.run_cmd")
    def test_clone(self, run_cmd):
        provider = DistGitProvider(self.source_json)
        provider.clone("/some/repo/directory")
        assert_cmd = ["git", "clone", "https://src.fedoraproject.org/git/rpms/389-admin-console.git",
                      "/some/repo/directory"]
        run_cmd.assert_called_with(assert_cmd)

    @mock.patch("rpmbuild.main.run_cmd")
    def test_checkout(self, run_cmd):
        provider = DistGitProvider(self.empty_source_json)
        provider.checkout("f25", "/some/repo/directory")
        assert_cmd = ["git", "checkout", "f25"]
        run_cmd.assert_called_with(assert_cmd, cwd="/some/repo/directory")

    def test_render_rpkg_template(self):
        provider = DistGitProvider(self.source_json)
        cfg = provider.render_rpkg_template()
        parser = ConfigParser.RawConfigParser()
        parser.readfp(StringIO.StringIO(cfg))
        self.assertEqual(parser.get("fedpkg", "lookaside"), "https://src.fedoraproject.org/repo/pkgs")
        self.assertEqual(parser.get("fedpkg", "lookaside_cgi"), "https://src.fedoraproject.org/repo/pkgs/upload.cgi")
        self.assertEqual(parser.get("fedpkg", "anongiturl"), "git://src.fedoraproject.org/%(module)s")

    def test_module_name(self):
        provider = DistGitProvider(self.empty_source_json)
        self.assertEqual(provider.module_name("/git/frostyx/hello/hello.git"), "frostyx/hello/hello")
        self.assertEqual(provider.module_name("/cgit/frostyx/hello/hello.git"), "frostyx/hello/hello")
        self.assertEqual(provider.module_name("http://copr-dist-git.fedorainfracloud.org/git/frostyx/hello/hello.git"),
                         "frostyx/hello/hello")

        self.assertEqual(provider.module_name("/git/rpms/hello.git"), "rpms/hello")
        self.assertEqual(provider.module_name("https://src.fedoraproject.org/git/rpms/hello.git"),
                         "rpms/hello")

    @mock.patch("rpmbuild.main.run_cmd")
    def test_produce_srpm(self, run_cmd):
        provider = DistGitProvider(self.source_json)
        provider.produce_srpm("/some/path/to/config", "myself/myproject/mypackage", "/some/repo/directory")
        assert_cmd = ["fedpkg", "--config", "/some/path/to/config",
                      "--module-name", "myself/myproject/mypackage", "srpm"]
        run_cmd.assert_called_with(assert_cmd, cwd="/some/repo/directory")
