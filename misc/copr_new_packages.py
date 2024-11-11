"""
This tool lists new packages in Copr, that are not yet available in Fedora.
It's main purpose is to help us pick new interesting projects for our Fedora
Magazine articles. See https://fedoramagazine.org/series/copr/
"""

import os
import subprocess
import argparse
from datetime import date, timedelta
from copr.v3 import Client
from tqdm import tqdm


# @TODO Check for package review RHBZ and print warnings.
#       Do not skip the project based on that


def get_new_projects(client, limit=1000):
    """
    Ideally we would like to get new projects since a given date - the date of
    finishing the latest released article, not its actual release date. Copr
    APIv3 doesn't allow us to do that (yet) so let's just take the last 1000
    projects and filter them on the client.
    """
    pagination = {"limit": limit, "order": "id", "order_type": "DESC"}
    projects = client.project_proxy.get_list(pagination=pagination)
    return projects


def pick_project_candidates(client, projects, since):
    """
    Filter only projects that might be worth investigating (e.g. for the Fedora
    Magazine article). By such projects we consider those with at least one
    succeeded build and at least some project information filled.
    """
    rawhide_pks_resp = subprocess.run(
        ["dnf", "--quiet", "--repo=fedora", "repoquery", "--queryformat", "%{name}\n", "*"],
        stdout=subprocess.PIPE,
    )
    fedora_rawhide_pkgs = {x for x in rawhide_pks_resp.stdout.decode().split()}

    picked = []
    for project in tqdm(projects):
        if project.unlisted_on_hp:
            tqdm.write("Skipping {}, it is unlisted on Copr homepage".format(project.full_name))
            continue

        if not any([project.description, project.instructions,
                    project.homepage, project.contact]):
            tqdm.write("Skipping {}, it has no information filled in".format(project.full_name))
            continue

        builds = client.build_proxy.get_list(project.ownername, project.name)
        if not builds:
            tqdm.write("Skipping {}, no builds".format(project.full_name))
            continue

        builds = [b for b in builds if b.state == "succeeded"]
        if not builds:
            tqdm.write("Skipping {}, no succeeded builds".format(project.full_name))
            continue

        builds = filter_unique_package_builds(builds)
        builds = [
            b for b in builds if b.source_package["name"] not in fedora_rawhide_pkgs
        ]
        if not builds:
            tqdm.write("Skipping {}, all packages already in Fedora".format(project.full_name))
            continue

        started_on = date.fromtimestamp(builds[-1].started_on)
        if started_on < since:
            tqdm.write("Reached older project than {}, ending with {}".format(since, project.full_name))
            break

        picked.append((project, builds))
    return picked


def filter_unique_package_builds(builds):
    """
    Return a list of builds where no two builds were submitted for the same
    pacakge. In case of duplicity, the build with higher ID is used.
    """
    unique = {}
    for build in sorted(builds, key=lambda x: x["id"]):
        packagename = build.source_package["name"]
        unique[packagename] = build
    return unique.values()


def get_parser():
    description = ("This tool lists new packages in Copr, that are not yet "
                   "available in Fedora. It's main purpose is to help us pick "
                   "new interesting projects for our Fedora Magazine articles. "
                   "See https://fedoramagazine.org/series/copr/")
    parser = argparse.ArgumentParser(__file__, description=description)
    parser.add_argument(
        "--since",
        required=False,
        default=date.today() - timedelta(days=31),
        type=date.fromisoformat,
        help="Search for new projects since YYYY-MM-DD",
    )
    parser.add_argument(
        "--limit",
        required=False,
        default=1000,
        type=int,
        help="Limit the number of projects to be checked",
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    client = Client.create_from_config_file()
    projects = get_new_projects(client, args.limit)

    print("Going to filter interesting projects since {}".format(args.since))
    print("This may take a while, ...")
    candidates = pick_project_candidates(client, projects, args.since)
    print("--------------------------")

    if not candidates:
        print("There are no interesting projects")

    for project, builds in candidates:
        print(project.full_name)
        print("  URL: {}".format(os.path.join(client.config["copr_url"], "coprs", project.full_name)))
        print("  Packages: {} ".format(" ".join([x.source_package["name"] for x in builds])))
        print("")


if __name__ == "__main__":
    main()
