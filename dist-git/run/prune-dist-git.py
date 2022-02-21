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
import time
import datetime
import copr

from copr.v3.client import Client as CoprClient

parser = argparse.ArgumentParser(description="Prune DistGit repositories and lookaside cache. "
                                             "Requires to be run as copr-dist-git user. "
                                             "You will be asked before anything is deleted. "
                                             "If you no longer want to be asked, answer 'Y', "
                                             "if you want to exit the script, answer 'N'.")
parser.add_argument('--repos', action='store', help='local path to a DistGit repository root', required=True)
parser.add_argument('--lookasidepkgs', action='store', help='local path to a DistGit lookaside cache pkgs root',
                    required=True)
parser.add_argument('--copr-config', action='store', help='path to copr config with API credentials', required=True)
parser.add_argument('--always-yes', action='store_true', help="Assume answer 'yes' for each deletion.")

args = parser.parse_args()


def get_build(username, copr_pr_dirname, client):
    """Get the last build in the given pr directory"""
    data = client.monitor_proxy.monitor(
        ownername=username, projectname=copr_pr_dirname.split(":")[0], project_dirname=copr_pr_dirname
    )
    build_id = None
    for pckg in data.packages:
        pckg_build_id = [b["build_id"] for b in pckg["chroots"].values()]
        if build_id is None:
            build_id = max(pckg_build_id)
            continue
        if max(pckg_build_id) > build_id:
            build_id = max(pckg_build_id)
    if build_id is None:
        return None
    return client.build_proxy.get(build_id)


def check_user():
    """Check under which user the program was run"""
    if pwd.getpwuid(os.getuid())[0] != "copr-dist-git":
        print("This script should be executed under the `copr-dist-git` user")
        sys.exit(1)


def process_dirname(pkgs_project_path, project_dirname, repos_project_path, username):
    """Directory doesn't exist so delete it"""
    answer = None
    if args.always_yes:
        answer = 'y'
    while not answer:
        a = input('Project {0}/{1} does not exist.\nDelete paths {2} and {3} [y/n]? '
                  .format(username, project_dirname, repos_project_path, pkgs_project_path))

        if a in ['n', 'no']:
            answer = 'n'
        if a in ['y', 'yes']:
            answer = 'y'
    if answer == 'y':
        print("Deleting {0}".format(repos_project_path))
        shutil.rmtree(repos_project_path, ignore_errors=True)
        print("Deleting {0}".format(pkgs_project_path))
        shutil.rmtree(pkgs_project_path, ignore_errors=True)


def main():
    """The main function that takes care of the whole logic"""
    check_user()
    client = CoprClient.create_from_config_file(args.copr_config)
    os.chdir(args.repos)
    if not os.path.isdir(args.repos):
        print("{0} is not a directory.".format(args.repos), file=sys.stderr)

    for username in os.listdir(args.repos):
        repos_user_path = os.path.join(args.repos, username)

        if not os.path.isdir(repos_user_path):
            continue

        for project_dirname in os.listdir(repos_user_path):
            repos_project_path = os.path.join(repos_user_path, project_dirname)

            # this is only an optimization, if the modified time of the package
            # directory has not changed in the last 90 days, then we perform an API check
            modified_time = 0
            for package in os.listdir(repos_project_path):
                mt = os.path.getmtime(os.path.join(repos_project_path, package))
                modified_time = max(modified_time, mt)

            if (datetime.datetime.today() - datetime.datetime.fromtimestamp(modified_time)).days < 90:
                continue

            try:
                if ":pr:" in project_dirname:
                    build = get_build(username, project_dirname, client)
                    if build and (
                            datetime.datetime.today() - datetime.datetime.fromtimestamp(build.ended_on)).days < 90:
                        continue
                else:
                    project_name = project_dirname.split(":", 1)[0]
                    client.project_proxy.get(username, project_name)
                    continue
            except copr.v3.exceptions.CoprNoResultException:
                pass
            except (copr.v3.exceptions.CoprRequestException, copr.v3.exceptions.CoprTimeoutException):
                print('Cannot connect to frontend. Pausing for 5 secs.')
                time.sleep(5)
                # this is run daily, no problem if we miss one
                # wait a few secs till frontend is available and continue
                continue

            pkgs_project_path = os.path.join(args.lookasidepkgs, username, project_dirname)
            process_dirname(pkgs_project_path, project_dirname, repos_project_path, username)


if __name__ == "__main__":
    main()
