#!/usr/bin/python3
import os
import subprocess
import re

lookaside_cache = "/var/lib/dist-git/cache/lookaside/pkgs"
git_dir = "/var/lib/dist-git/git"

for user in os.listdir(lookaside_cache):
    for project in os.listdir(os.path.join(lookaside_cache, user)):
        for package in os.listdir(os.path.join(lookaside_cache, user, project)):
            pkg_git_dir = os.path.join(git_dir, user, project, package + ".git")
            pkg_lookaside_dir = os.path.join(lookaside_cache, user, project, package)
            # TODO use the script from dist-git once it's merged there
            subprocess.call(['/usr/bin/copr-prune-dist-git-sources', pkg_git_dir, pkg_lookaside_dir])
