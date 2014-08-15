#-*- coding: UTF-8 -*-

__version__ = "0.3.0"
__description__ = "CLI tool to run copr"

import argparse
import sys
import ConfigParser
import datetime
import time
from collections import defaultdict

from copr_client import CoprClient
import copr_client.exceptions as copr_exceptions

client = CoprClient.create_from_file_config()


def _watch_builds(build_ids):
    print("Watching build(s): (this may be safely interrupted)")
    prevstatus = defaultdict(lambda: None)
    failed_ids = []
    watched_ids = build_ids[:]

    try:
        while True:
            for build_id in watched_ids:
                build_status = client.get_build_status(build_id)
                if build_status.output != "ok":
                    errmsg = "  Build {1}: Unable to get build status: {0}".format(
                        build_status.error, build_id)
                    raise copr_exceptions.CoprRequestException(errmsg)

                now = datetime.datetime.now()
                if prevstatus[build_id] != build_status.status:
                    prevstatus[build_id] = build_status.status
                    print("  {0} Build {2}: {1}".format(
                        now.strftime("%H:%M:%S"),
                        build_status.status, build_id))

                if build_status.status in ["failed"]:
                    failed_ids.append(build_id)
                if build_status.status in ["succeeded", "skipped",
                                           "failed", "canceled"]:
                    watched_ids.remove(build_id)
                if build_status.status == "unknown":
                    raise copr_exceptions.CoprBuildException(
                        "Unknown status.")

            if not watched_ids:
                break
            time.sleep(60)

        if failed_ids:
            raise copr_exceptions.CoprBuildException(
                    "Build(s) {0} failed.".format(
                    ", ".join(str(x) for x in failed_ids)))

    except KeyboardInterrupt:
        pass


def action_build(args):
    """ Method called when the 'build' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    result = client.create_new_build(
        projectname=args.copr, chroots=args.chroots, pkgs=args.pkgs,
        memory=args.memory, timeout=args.timeout)
    if result.output != "ok":
        print(result.error)
        return
    print(result.message)
    print("Created builds: {0}".format(" ".join(map(str, result.ids))))

    if not args.nowait:
        _watch_builds(result.ids)


def action_create(args):
    """ Method called when the 'create' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    result = client.create_project(
        projectname=args.name, description=args.description,
        instructions=args.instructions, chroots=args.chroots,
        repos=args.repos, initial_pkgs=args.initial_pkgs)
    print(result)


def action_delete(args):
    """ Method called when the 'delete' action has been selected by the
    user.

    :param args: argparse arguments provided by the user
    """
    result = client.delete_project(projectname=args.copr)
    print(result)


def action_list(args):
    """ Method called when the 'list' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    username = args.username or client.username
    result = client.get_projects_list(username)
    if result.response["output"] != "ok":
        print(result.error)
        print("Un-expected data returned, please report this issue")
    elif not result.projects:
        print("No copr retrieved for user: '{0}'".format(username))
        return

    for prj in result.projects:
        print(prj)


def action_status(args):
    result = client.get_build_status(args.build_id)
    print(result)


def action_cancel(args):
    """ Method called when the 'cancel' action has been selected by the
    user.
    :param args: argparse arguments provided by the user
    """
    result = client.cancel_build(args.build_id)
    print(result)

def setup_parser():
    """
    Set the main arguments.
    """
    parser = argparse.ArgumentParser(prog="copr-cli")
    # General connection options
    parser.add_argument("--version", action="version",
                        version="copr-cli {0}".format(__version__))

    subparsers = parser.add_subparsers(title="actions")

    # create the parser for the "list" command
    parser_list = subparsers.add_parser("list",
                                        help="List all the copr of the "
                                             "provided "
                                        )
    parser_list.add_argument("username", nargs="?",
                             help="The username that you would like to "
                             "list the copr of (defaults to current user)"
                             )
    parser_list.set_defaults(func=action_list)

    # create the parser for the "create" command
    parser_create = subparsers.add_parser("create",
                                          help="Create a new copr")
    parser_create.add_argument("name",
                               help="The name of the copr to create")
    parser_create.add_argument("--chroot", dest="chroots", action="append",
                               help="Chroot to use for this copr")
    parser_create.add_argument("--repo", dest="repos", action="append",
                               help="Repository to add to this copr")
    parser_create.add_argument("--initial-pkgs", dest="initial_pkgs",
                               action="append",
                               help="List of packages URL to build in this "
                                    "new copr")
    parser_create.add_argument("--description",
                               help="Description of the copr")
    parser_create.add_argument("--instructions",
                               help="Instructions for the copr")
    parser_create.set_defaults(func=action_create)

    # create the parser for the "delete" command
    parser_delete = subparsers.add_parser("delete",
                                          help="Deletes the entire project")
    parser_delete.add_argument("copr",
                              help="Name of your project to be deleted.")
    parser_delete.set_defaults(func=action_delete)

    # create the parser for the "build" command
    parser_build = subparsers.add_parser("build",
                                         help="Build packages to a "
                                         "specified copr")
    parser_build.add_argument("copr",
                              help="The copr repo to build the package in. Can just name of project or even in format username/project."
                              )
    parser_build.add_argument("pkgs", nargs="+",
                              help="URL of packages to build")
    parser_build.add_argument("-r", "--chroot", dest="chroots", action="append",
                               help="If you don't need this build for all the project's chroots. You can use it several times for each chroot you need.")
    parser_build.add_argument("--memory", dest="memory",
                              help="")
    parser_build.add_argument("--timeout", dest="timeout",
                              help="")
    parser_build.add_argument("--nowait", action="store_true", default=False,
                              help="Don't wait for build")
    parser_build.set_defaults(func=action_build)

    # create the parser for the "status" command
    parser_build = subparsers.add_parser("status",
                                         help="Get build status of build"
                                         " specified by its ID")
    parser_build.add_argument("build_id",
                              help="Build ID")
    parser_build.set_defaults(func=action_status)

    # create the parser for the "cancel" command
    parser_build = subparsers.add_parser("cancel",
        help="Cancel build specified by its ID")
    parser_build.add_argument("build_id",
                              help="Build ID")
    parser_build.set_defaults(func=action_cancel)

    return parser


def main(argv=sys.argv[1:]):
    try:
        # Set up parser for global args
        parser = setup_parser()
        # Parse the commandline
        arg = parser.parse_args()
        arg.func(arg)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.")
        sys.exit(1)
    except copr_exceptions.CoprRequestException, e:
        sys.stderr.write("\nSomething went wrong:")
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(1)
    except argparse.ArgumentTypeError, e:
        sys.stderr.write("\nError: {0}".format(e))
        sys.exit(2)
    except copr_exceptions.CoprException, e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(3)
    except ConfigParser.ParsingError, e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.stderr.write("Lines in INI file should not be indented.\n")
        sys.exit(3)
    except copr_exceptions.CoprBuildException, e:
        sys.stderr.write("\nBuild error: {0}\n".format(e))
        sys.exit(4)
    except copr_exceptions.CoprUnknownResponseException, e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(5)
    # except Exception as e:
        # print "Error: {0}".format(e)
        # sys.exit(100)


if __name__ == "__main__":
    main()
