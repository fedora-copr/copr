#!/usr/bin/python3

"""
One-shot script to remove data on copr-dist-git for already deleted coprs.
Should be run as copr-dist-git user.
"""

import os
import shutil
import sys
import pwd
import argparse
import copr

from copr.v3.client import Client as CoprClient

parser = argparse.ArgumentParser(description="Prune DistGit repositories and lookaside cache. "
                                 "Requires to be run as copr-dist-git user. You will be asked before anything is deleted. "
                                 "If you no longer want to be asked, answer 'Y', if you want to exit the script, answer 'N'.")
parser.add_argument('--repos', action='store', help='local path to a DistGit repository root', required=True)
parser.add_argument('--pkgs', action='store', help='local path to a DistGit lookaside cache pkgs root', required=True)
parser.add_argument('--copr-config', action='store', help='path to copr config with API credentials', required=True)

args = parser.parse_args()

if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr-dist-git":
        print("This script should be executed under the `copr-dist-git` user")
        sys.exit(1)

    client = CoprClient.create_from_config_file(args.copr_config)
    os.chdir(args.repos)

    always_yes = False

    if not os.path.isdir(args.repos):
        print("{0} is not a directory.".format(args.repos), file=sys.stderr)

    for username in os.listdir(args.repos):
        repos_user_path = os.path.join(args.repos, username)

        if not os.path.isdir(repos_user_path):
            continue

        for projectname in os.listdir(repos_user_path):
            repos_project_path = os.path.join(repos_user_path, projectname)

            try:
                client.project_proxy.get(username, projectname)
            except copr.v3.exceptions.CoprNoResultException:
                pass
            else:
                continue

            pkgs_project_path = os.path.join(args.pkgs, username, projectname)

            answer = None
            if always_yes:
                answer = 'y'

            while not answer:
                a = input('Project {0}/{1} does not exist.\nDelete paths {2} and {3} [y/n/Y/N]? '
                          .format(username, projectname, repos_project_path, pkgs_project_path))

                if a == 'n' or a == 'no':
                    answer = 'n'
                if a == 'y' or a == 'yes':
                    answer = 'y'

                if a == 'Y' or a == 'YES':
                    always_yes = True
                    answer = 'y'
                if a == 'N' or a == 'NO':
                    sys.exit(1)

            if answer == 'y':
                print("Deleting {0}".format(repos_project_path))
                shutil.rmtree(repos_project_path, ignore_errors=True)
                print("Deleting {0}".format(pkgs_project_path))
                shutil.rmtree(pkgs_project_path, ignore_errors=True)
