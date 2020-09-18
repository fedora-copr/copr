"""
copr-distgit-client testsuite
"""

import os
import shutil
import tempfile
try:
    from unittest import mock
except ImportError:
    import mock

from copr_distgit_client import sources, srpm, _load_config, check_output

# pylint: disable=useless-object-inheritance

def init_git(files=None):
    """ Initialize .git/ directory """

    check_output(["git", "init", "."])
    shutil.rmtree(".git/hooks")
    check_output(["git", "config", "user.email", "you@example.com"])
    check_output(["git", "config", "user.name", "Your Name"])
    check_output(["git", "config", "advice.detachedHead", "false"])

    for filename, content in files:
        dirname = os.path.dirname(filename)
        try:
            os.makedirs(dirname)
        except OSError:
            pass
        with open(filename, "w") as filed:
            filed.write(content)
        check_output(["git", "add", filename])

    check_output(["git", "commit", "-m", "initial"])


def git_origin_url(url):
    """ setup .git/config with core.origin.url == URL """
    with open(".git/config", "a+") as gcf:
        gcf.write('[remote "origin"]\n')
        gcf.write('url = {0}\n'.format(url))


class TestDistGitDownload(object):
    """ Test the 'sources()' method """
    config = None
    args = None
    workdir = None

    def setup_method(self, method):
        _unused_but_needed_for_el6 = (method)
        testdir = os.path.dirname(__file__)
        projdir = os.path.dirname(testdir)
        config_dir = os.path.join(projdir, 'etc/copr-distgit-client')
        self.config = _load_config(config_dir)
        class _Args:
            # pylint: disable=too-few-public-methods
            dry_run = False
        self.args = _Args()
        self.workdir = tempfile.mkdtemp(prefix="copr-distgit-test-")
        os.chdir(self.workdir)

    def teardown_method(self, method):
        _unused_but_needed_for_el6 = (method)
        shutil.rmtree(self.workdir)


    @mock.patch('copr_distgit_client.download_file_and_check')
    def test_copr_distgit(self, download):
        init_git([
            ("test.spec", ""),
            ("sources", "2102fd0602de72e58765adcbf92349d8 retrace-server-git-955.3e4742a.tar.gz\n"),
        ])
        git_origin_url("https://copr-dist-git.fedorainfracloud.org/git/@abrt/retrace-server-devel/retrace-server.git")
        sources(self.args, self.config)
        assert len(download.call_args_list) == 1
        assert download.call_args_list[0][0][0] == (
            "https://copr-dist-git.fedorainfracloud.org/repo/pkgs/"
            "@abrt/retrace-server-devel/test/retrace-server-git-955.3e4742a.tar.gz/"
            "md5/2102fd0602de72e58765adcbf92349d8/retrace-server-git-955.3e4742a.tar.gz"
        )

    @mock.patch('copr_distgit_client.download_file_and_check')
    def test_fedora_old(self, download):
        """
        Old sources format + ssh clone
        """
        init_git([
            ("tar.spec", ""),
            ("sources", "0ced6f20b9fa1bea588005b5ad4b52c1  tar-1.26.tar.xz\n"),
        ])
        git_origin_url("ssh://praiskup@pkgs.fedoraproject.org/rpms/tar")
        sources(self.args, self.config)
        assert len(download.call_args_list) == 1
        assert download.call_args_list[0][0][0] == (
            "https://src.fedoraproject.org/repo/pkgs/rpms/"
            "tar/tar-1.26.tar.xz/md5/0ced6f20b9fa1bea588005b5ad4b52c1/tar-1.26.tar.xz"
        )

    @mock.patch('copr_distgit_client.download_file_and_check')
    def test_fedora_new(self, download):
        """
        New sources format + anonymous clone
        """
        sha512 = (
            "1bd13854009b6ee08958481738e6bf661e40216a2befe461d06b4b350eb882e43"
            "1b3a4eeea7ca1d35d37102df76194c9d933df2b18b3c5401350e9fc17017750"
        )
        init_git([
            ("tar.spec", ""),
            ("sources", "SHA512 (tar-1.32.tar.xz) = {0}\n".format(sha512)),
        ])
        git_origin_url("https://src.fedoraproject.org/rpms/tar.git")
        sources(self.args, self.config)
        assert len(download.call_args_list) == 1
        url = (
            "https://src.fedoraproject.org/repo/pkgs/rpms/"
            "tar/tar-1.32.tar.xz/sha512/{sha512}/tar-1.32.tar.xz"
        ).format(sha512=sha512)
        assert download.call_args_list[0][0][0] == url

    @mock.patch('copr_distgit_client.download_file_and_check')
    def test_centos(self, download):
        """
        Anonymous centos clone
        """
        init_git([
            ("SPECS/centpkg-minimal.spec", ""),
            (".centpkg-minimal.metadata", "cf9ce8d900768ed352a6f19a2857e64403643545 SOURCES/centpkg-minimal.tar.gz\n"),
        ])
        git_origin_url("https://git.centos.org/rpms/centpkg-minimal.git")
        sources(self.args, self.config)
        assert len(download.call_args_list) == 1
        assert download.call_args_list[0][0][0] == (
            "https://git.centos.org/sources/centpkg-minimal/master/"
            "cf9ce8d900768ed352a6f19a2857e64403643545"
        )
        assert download.call_args_list[0][0][2]["sources"] == "SOURCES"
        assert download.call_args_list[0][0][1]["hashtype"] == "sha1"

        oldref = check_output(["git", "rev-parse", "HEAD"]).decode("utf-8")
        oldref = oldref.strip()

        # create new commit, and checkout back (so --show-current is not set)
        check_output(["git", "commit", "--allow-empty", "-m", "empty"])
        check_output(["git", "checkout", "-q", oldref])

        sources(self.args, self.config)
        assert download.call_args_list[1][0][0] == (
            "https://git.centos.org/sources/centpkg-minimal/{0}/"
            "cf9ce8d900768ed352a6f19a2857e64403643545"
        ).format(oldref)


    @mock.patch("copr_distgit_client.subprocess.check_call")
    def test_centos_download(self, patched_check_call):
        init_git([
            ("SPECS/centpkg-minimal.spec", ""),
            (".centpkg-minimal.metadata", "cf9ce8d900768ed352a6f19a2857e64403643545 SOURCES/centpkg-minimal.tar.gz\n"),
        ])
        git_origin_url("https://git.centos.org/rpms/centpkg-minimal.git")
        setattr(self.args, "outputdir", os.path.join(self.workdir, "result"))
        setattr(self.args, "mock_chroot", None)
        srpm(self.args, self.config)
        assert patched_check_call.call_args_list[0][0][0] == [
            'rpmbuild', '-bs',
            os.path.join(self.workdir, "SPECS", "centpkg-minimal.spec"),
            '--define', 'dist %nil',
            '--define', '_sourcedir ' + self.workdir + '/SOURCES',
            '--define', '_srcrpmdir ' + self.workdir + '/result',
            '--define', '_disable_source_fetch 1',
        ]
