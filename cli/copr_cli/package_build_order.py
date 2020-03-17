#!/usr/bin/python3
"""List packages of a given copr project in the order in which they were built."""

import os
import sys
import argparse
from configparser import ConfigParser

from copr.v3 import BuildProxy, BuildChrootProxy, config_from_file
from copr.v3.exceptions import CoprNoConfigException, CoprNoResultException, CoprRequestException

from koji import ClientSession, GenericError, BUILD_STATES


def package_order_from_copr(args):
    """List package build order from Copr"""
    if not args.project:
        print("You need to specify Copr project to list package build order.")
        sys.exit(1)

    if not args.config:
        args.config = "~/.config/copr"

    try:
        config_file = config_from_file(args.config)
    except CoprNoConfigException:
        print("Couldn't find copr config file at {0}.".format(args.config))
        sys.exit(1)

    try:
        build_proxy = BuildProxy(config_file)
        build_chroot_proxy = BuildChrootProxy(config_file)
        project = args.project.split("/")
        username = project[0]
        projectname = project[1]
        build_list = build_proxy.get_list(username, projectname)
    except CoprNoResultException:
        print("No copr project {0}/{1}.".format(username, projectname))
        sys.exit(1)
    except CoprRequestException:
        print("Failed to get information from Copr.")
        sys.exit(1)

    build_list.reverse()
    processed_packages = []
    for build in build_list:
        if args.chroot and args.chroot not in build["chroots"]:
            continue
        if build["state"] != "succeeded":
            if not args.chroot:
                continue
            if len(build["chroots"]) == 1:
                continue
            build_chroot = build_chroot_proxy.get(build["id"], args.chroot)
            if build_chroot.state != "succeeded":
                continue

        package = "{0}-{1}".format(build["source_package"]["name"], build["source_package"]["version"])
        if not package:
            continue
        if not args.list_each:
            if package in processed_packages:
                continue
            processed_packages.append(package)

        print(package)


def package_order_from_koji(args):
    """List package build order from Koji"""
    if not args.username and not args.tag:
        print("You need to specify either username or tag to list build order in Koji.")
        sys.exit(1)

    for path in [args.config, "~/.config/koji", "/etc/koji.conf"]:
        if path and os.path.exists(path):
            args.config = path

    if not args.config:
        print("Couldn't find koji config file.")

    config_file = ConfigParser()
    config_file.read(args.config)

    koji_url = config_file.get("koji", "server")
    session = ClientSession(koji_url)

    if args.tag:
        try:
            builds = session.listTagged(tag=args.tag, owner=args.username)
        except GenericError:
            print("No tag {0}.".format(args.tag))
            sys.exit(1)

    elif args.username:
        user = session.getUser(args.username)
        if not user:
            print("No user {0}.".format(args.username))
            sys.exit(1)

        user_id = user["id"]
        builds = session.listBuilds(userID=user_id)

    processed_packages = []
    for build in sorted(builds, key=lambda i: i["completion_time"]):
        if build["state"] != BUILD_STATES["COMPLETE"]:
            continue
        package = build["nvr"]
        if not package:
            continue
        if not args.list_each:
            if package in processed_packages:
                continue
            processed_packages.append(package)

        print(package)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help="Path to copr/koji config")
    parser.add_argument("--list-each", "-e", action="store_true", default=False,
                        help="List each occurence of every package in the project")

    subparsers = parser.add_subparsers(title="commands")

    parser_copr = subparsers.add_parser("copr", help="List package build order in Copr")
    parser_copr.add_argument("--project", "-p", type=str, help="Copr project in `owner/project` format")
    parser_copr.add_argument("--chroot", "-c", type=str, help="List this chroot only")
    parser_copr.set_defaults(func=package_order_from_copr)

    parser_koji = subparsers.add_parser("koji", help="List package build order in Koji")
    parser_koji.add_argument("--username", "-u", type=str, help="Koji username")
    parser_koji.add_argument("--tag", "-t", type=str, help="Koji tag")
    parser_koji.set_defaults(func=package_order_from_koji)

    args = parser.parse_args()
    try:
        args.func(args)
    except AttributeError:
        parser.print_help()
        sys.exit(0)
