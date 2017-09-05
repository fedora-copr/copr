import unittest
import mock
import configparser
from io import StringIO
from os.path import realpath, dirname
from ..copr_rpmbuild.providers.distgit import DistGitProvider


class TestDistGitProvider(unittest.TestCase):
    def setUp(self):
        self.source_json = {"clone_url": "https://src.fedoraproject.org/git/rpms/389-admin-console.git",
                            "branch": "f25"}
        self.empty_source_json = {"clone_url": None, "branch": None}

    def test_init(self):
        provider = DistGitProvider(self.source_json)
        self.assertEqual(provider.clone_url, "https://src.fedoraproject.org/git/rpms/389-admin-console.git")
        self.assertEqual(provider.branch, "f25")

    @mock.patch("rpmbuild.copr_rpmbuild.providers.distgit.run_cmd")
    def test_clone(self, run_cmd):
        provider = DistGitProvider(self.source_json)
        provider.clone("/some/repo/directory")
        assert_cmd = ["git", "clone", "https://src.fedoraproject.org/git/rpms/389-admin-console.git",
                      "/some/repo/directory"]
        run_cmd.assert_called_with(assert_cmd)

    @mock.patch("rpmbuild.copr_rpmbuild.providers.distgit.run_cmd")
    def test_checkout(self, run_cmd):
        provider = DistGitProvider(self.empty_source_json)
        provider.checkout("f25", "/some/repo/directory")
        assert_cmd = ["git", "checkout", "f25"]
        run_cmd.assert_called_with(assert_cmd, cwd="/some/repo/directory")

    def test_render_rpkg_template(self):
        confdirs = [dirname(dirname(realpath(__file__)))]
        provider = DistGitProvider(self.source_json, confdirs=confdirs)
        cfg = provider.render_rpkg_template()
        parser = configparser.RawConfigParser()
        parser.readfp(StringIO(cfg))
        self.assertEqual(parser.get("rpkg", "lookaside"), "https://src.fedoraproject.org/repo/pkgs")
        self.assertEqual(parser.get("rpkg", "lookaside_cgi"), "https://src.fedoraproject.org/repo/pkgs/upload.cgi")
        self.assertEqual(parser.get("rpkg", "anongiturl"), "git://src.fedoraproject.org/%(module)s")

    def test_module_name(self):
        provider = DistGitProvider(self.empty_source_json)
        self.assertEqual(provider.module_name("/git/frostyx/hello/hello.git"), "frostyx/hello/hello")
        self.assertEqual(provider.module_name("/cgit/frostyx/hello/hello.git"), "frostyx/hello/hello")
        self.assertEqual(provider.module_name("http://copr-dist-git.fedorainfracloud.org/git/frostyx/hello/hello.git"),
                         "frostyx/hello/hello")

        self.assertEqual(provider.module_name("/git/rpms/hello.git"), "rpms/hello")
        self.assertEqual(provider.module_name("https://src.fedoraproject.org/git/rpms/hello.git"),
                         "rpms/hello")

    @mock.patch("rpmbuild.copr_rpmbuild.providers.distgit.run_cmd")
    def test_produce_srpm(self, run_cmd):
        provider = DistGitProvider(self.source_json)
        provider.produce_srpm("/some/path/to/config", "myself/myproject/mypackage", "/some/repo/directory")
        assert_cmd = ["rpkg", "--config", "/some/path/to/config",
                      "--module-name", "myself/myproject/mypackage", "srpm"]
        run_cmd.assert_called_with(assert_cmd, cwd="/some/repo/directory")

    @mock.patch("os.listdir")
    def test_srpm(self, listdir):
        listdir.return_value = ["389-admin-console.spec", "389-admin-console-1.1.12.tar.bz2",
                                "389-admin-console-1.1.12-1.fc26.src.rpm", "sources"]
        provider = DistGitProvider(self.empty_source_json, workdir="/some/repo/directory")
        self.assertEqual(provider.srpm, "/some/repo/directory/repo/389-admin-console-1.1.12-1.fc26.src.rpm")
