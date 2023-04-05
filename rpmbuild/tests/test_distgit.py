"""
Test the DistGit provider
"""

import os
import shutil
import subprocess
import tempfile

import configparser
import pytest

from copr_distgit_client import check_output
from copr_rpmbuild.providers.distgit import DistGitProvider
from copr_rpmbuild.helpers import git_clone_and_checkout

try:
    from unittest import mock
except ImportError:
    # Python 2 version depends on mock
    import mock

from tests.test_distgit_client import init_git
from tests import TestCase

class TestDistGitProvider(TestCase):
    olddir = None
    workdir = None
    origin = None
    outdir = None
    configdir = None
    lookaside = None
    env_patch = None
    main_config = None

    def _setup_configdir(self):
        self.configdir = os.path.join(self.workdir, "configdir")
        os.mkdir(self.configdir)

        config = """\n
[lllocal]
clone_hostnames = localhost
lookaside_location = file://{workdir}
lookaside_uri_pattern = lookaside/{{filename}}
""".format(workdir=self.workdir)
        with open(os.path.join(self.configdir, "default.ini"), "w+") as fdc:
            fdc.write(config)

        self.env_patch = mock.patch.dict(os.environ, {
            "COPR_DISTGIT_CLIENT_CONFDIR": self.configdir,
            "COPR_DISTGIT_CLIENT_DRY_RUN": "true",
        })
        self.env_patch.start()

    def setup_method(self, method):
        _unused_but_needed_for_el6 = (method)
        self.workdir = tempfile.mkdtemp(prefix="copr-distgit-provider-test-")
        self.origin = os.path.join(self.workdir, "origin.git")
        os.mkdir(self.origin)
        os.chdir(self.origin)
        self.lookaside = os.path.join(self.workdir, "lookaside")
        os.mkdir(self.lookaside)
        datafile = os.path.join(self.lookaside, "datafile")
        with open(datafile, "w") as fdd:
            fdd.write("data content\n")

        output = check_output(['md5sum', datafile])
        md5 = output.decode("utf-8").strip().split(' ')[0]
        init_git([
            ("test.spec", "specfile_content\n"),
            ("sources", "{md5} datafile\n".format(md5=md5)),
        ])
        self._setup_configdir()

        self.main_config = mc = configparser.ConfigParser()
        mc.add_section("main")
        mc.set("main", "enabled_source_protocols", "file")
        mc.set("main", "resultdir", os.path.join(self.workdir, "results"))
        mc.set("main", "workspace", os.path.join(self.workdir, "workspace"))

        # these normally exist
        os.makedirs(mc.get("main", "resultdir"))
        os.makedirs(mc.get("main", "workspace"))


    def teardown_method(self, method):
        _unused_but_needed_for_el6 = (method)
        shutil.rmtree(self.workdir)
        self.env_patch.stop()

    def test_distgit_method(self):
        source_dict = {"clone_url": self.origin}
        dgp = DistGitProvider(source_dict, self.main_config)
        # this is normally created in main.py
        dgp.produce_srpm()

        # check presence of the cloned file
        cloned_file = os.path.join(dgp.workdir, "origin", "datafile")
        assert os.path.exists(cloned_file)

    def test_remote_refs(self):
        os.chdir(self.workdir)
        cmd = """
set -xe
mkdir origin-bare && cd origin-bare
git init --bare
cd ..
git clone origin-bare modifying-clone
cd modifying-clone
git config user.email "you@example.com"
git config user.name "Your Name"
git checkout -b pr
git commit --allow-empty -m 'new commit'
git push -u origin pr
cd ../origin-bare
mkdir -p refs/pull/50/
mv refs/heads/pr refs/pull/50/head
"""
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as err:
            if hasattr(err, "stdout"):
                print(err.stdout.decode("utf-8"))
            else:
                print(str(err))
            raise

        clone_url = "file://" + os.path.join(os.getcwd(), "origin-bare")
        dest = os.path.join(self.workdir, "dest")
        os.makedirs(dest)
        git_clone_and_checkout(clone_url, "refs/pull/50/head", dest)


@pytest.mark.parametrize('committish', ["main", None, ""])
@mock.patch("copr_rpmbuild.helpers.run_cmd")
def test_with_without_committish(run_cmd, committish):
    git_clone_and_checkout("clone_url", committish, "/dir")
    expected = []
    expected += [mock.call(['git', 'clone', 'clone_url', '/dir', '--depth',
                            '500', '--no-single-branch', '--recursive'])]
    if committish:
        expected += [mock.call(['git', 'checkout', committish], cwd='/dir')]

    assert expected == run_cmd.call_args_list
