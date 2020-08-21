"""
Test the DistGit provider
"""

import os
import shutil
import tempfile

import configparser

from copr_distgit_client import check_output
from copr_rpmbuild.providers.distgit import DistGitProvider

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
        self.outdir = os.path.join(self.workdir, "out")
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

        self.main_config = configparser.ConfigParser()
        self.main_config.add_section("main")
        self.main_config.set("main", "enabled_source_protocols", "file")

    def teardown_method(self, method):
        _unused_but_needed_for_el6 = (method)
        shutil.rmtree(self.workdir)
        self.env_patch.stop()

    def test_distgit_method(self):
        os.mkdir(self.outdir)
        source_dict = {"clone_url": self.origin}
        dgp = DistGitProvider(source_dict, self.outdir, self.main_config)
        dgp.produce_srpm()
        assert os.path.exists(os.path.join(self.outdir, "obtain-sources",
                                           "origin", "datafile"))
