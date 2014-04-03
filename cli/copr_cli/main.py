#-*- coding: UTF-8 -*-

import argparse
import sys
import ConfigParser

import subcommands
import copr_exceptions

__version__ = "0.2.0"
__description__ = "CLI tool to run copr"


def action_build(args):
    """ Method called when the 'build' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    subcommands.build(args.copr, args.pkgs,
                      args.memory, args.timeout, not args.nowait, chroots=args.chroots)


def action_create(args):
    """ Method called when the 'create' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    subcommands.create(args.name, args.chroots, args.description,
                       args.instructions, args.repos,
                       args.initial_pkgs)


def action_list(args):
    """ Method called when the 'list' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    subcommands.listcoprs(args.username)


def action_status(args):
    subcommands.status(args.build_id)

def action_cancel(args):
    """ Method called when the 'cancel' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    subcommands.cancel(args.build_id)

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
    except argparse.ArgumentTypeError, e:
        sys.stderr.write("\nError: {0}".format(e))
        sys.exit(2)
    except copr_exceptions.CoprCliException, e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(3)
    except ConfigParser.ParsingError, e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.stderr.write("Lines in INI file should not be indented.\n")
        sys.exit(4)
    # except Exception as e:
        # print "Error: {0}".format(e)
        # sys.exit(100)


if __name__ == "__main__":
    main()
