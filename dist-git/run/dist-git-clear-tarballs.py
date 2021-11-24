#!/usr/bin/python3

"""
One-shot script to remove all tarballs in <package_lookaside_directory> except
for tarballs that are referenced by the latest commit of each branch in <package_git_directory>.
Should be run as copr-dist-git user.
"""

import os
import sys
import pwd
import logging
from configparser import ConfigParser

from copr_dist_git.helpers import run_cmd, ConfigReader
from copr_common.tree import walk_limited
from copr_dist_git.exceptions import RunCommandException

log = logging.getLogger(__name__)


def clear_tarballs(git_repository_root, lookaside_location):
    for project_path, package_git_dirs, _ in walk_limited(git_repository_root, mindepth=2, maxdepth=2):
        for package_git_dir in package_git_dirs:
            package_name = package_git_dir.removesuffix(".git")
            repos_path = os.path.join(project_path, package_git_dir)
            username_projectname = os.path.relpath(project_path, git_repository_root)
            lookasidepkgs_path = os.path.join(lookaside_location, username_projectname, package_name)
            result = None
            try:
                result = run_cmd(['remove_unused_sources', repos_path, lookasidepkgs_path])
            except RunCommandException:
                log.debug(result)


if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr-dist-git":
        print("This script should be executed under the `copr-dist-git` user")
        sys.exit(1)
    config_parser = ConfigParser()
    config_parser.read("/etc/dist-git/dist-git.conf")
    dist_git_section = config_parser["dist-git"]
    gitroot_dir = dist_git_section.get("gitroot_dir", "/var/lib/dist-git/git/")
    config_reader = ConfigReader("/etc/copr/copr-dist-git.conf")
    opts = config_reader.read()
    logging.basicConfig(
        filename=os.path.join(opts.log_dir, "cleanup-tarballs.log"),
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d][pid:%(process)d] %(message)s',
        datefmt='%H:%M:%S'
    )
    clear_tarballs(gitroot_dir, opts.lookaside_location)
