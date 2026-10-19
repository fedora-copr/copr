"""
The "Build package from DistGit" method
"""

import os
from copr_rpmbuild import helpers
from .base import Provider


class DistGitProvider(Provider):
    """
    DistGit provider, wrapper around the dist-git-client script
    """

    clone_url = None
    committish = None
    clone_to = None
    forked_from = None

    def init_provider(self):
        self.clone_url = self.source_dict["clone_url"]
        self.committish = self.source_dict.get("committish")
        self.forked_from = self.source_dict.get("forked_from")
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
        helpers.run_cmd(self.distgit_client_cmd(["sources"]),
                        cwd=self.clone_to)

    def produce_srpm(self):
        self.produce_sources()
        helpers.run_cmd(
            self.distgit_client_cmd(["srpm", "--outputdir", self.resultdir]),
            cwd=self.clone_to,
        )

    def distgit_client_cmd(self, args):
        """
        Assemble the dist-git-client command, e.g. ["sources"] or
        ["srpm", "--outputdir", ...].  When the DistGit repository we build from is a
        fork, prefix the command with the --forked-from option that tells
        dist-git-client to use the given URL (instead of the one detected from
        the .git/config file) for detecting the appropriate lookaside cache.
        """
        cmd = ["dist-git-client"]
        if self.forked_from:
            cmd += ["--forked-from", self.forked_from]
        return cmd + args
