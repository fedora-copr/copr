"""
The "Build package from DistGit" method
"""

import os

from copr_rpmbuild import helpers
from copr_rpmbuild.providers.base import Provider


class DistGitProvider(Provider):
    """
    DistGit provider, wrapper around copr-distgit-client script
    """
    def __init__(self, source_dict, outdir, config):
        super(DistGitProvider, self).__init__(source_dict, outdir, config)
        self.clone_url = source_dict["clone_url"]
        self.committish = source_dict.get("committish")
        self.clone_to = os.path.join(
            self.workdir,
            helpers.git_clone_url_basepath(self.clone_url))

    def produce_sources(self):
        """
        Clone and download sources from DistGit lookaside cache.

        We define this helper function on top of Provider() API because we use
        the DistGit method on two places; first as a normal "source method", and
        second for getting sources from our own "proxy" DistGit instance.
        """
        helpers.git_clone_and_checkout(self.clone_url, self.committish,
                                       self.clone_to)
        helpers.run_cmd(["copr-distgit-client", "sources"], cwd=self.clone_to)

    def produce_srpm(self):
        self.produce_sources()
        helpers.run_cmd([
            "copr-distgit-client", "srpm", "--outputdir", self.outdir
        ], cwd=self.clone_to)
