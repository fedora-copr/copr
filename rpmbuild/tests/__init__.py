import os
import tempfile
import unittest

from copr_rpmbuild import helpers

CONFIG = """
[main]
frontend_url = https://copr.fedoraproject.org
resultdir = /var/lib/copr-rpmbuild/results
enabled_source_protocols = https ftps

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

class TestCase(unittest.TestCase):
    def test_setup(self):
        # to be defined in child class
        pass

    def setUp(self):
        self.config_path, self.config = self.read_config_data(CONFIG)
        self.test_setup()

    def tearDown(self):
        os.unlink(self.config_path)

    def read_config_data(self, config_data):
        fd, config_path = tempfile.mkstemp()
        f = open(config_path, 'w')
        f.write(config_data)
        f.close()
        return config_path, helpers.read_config(config_path)
