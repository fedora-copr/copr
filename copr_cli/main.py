#-*- coding: UTF-8 -*-

import argparse
import sys

import subcommands

__version__ = '0.1.0'
__description__ = "CLI tool to run copr"


def action_build(args):
    """ Method called when the 'build' action has been selected by the
    user.

    :param args: argparse arguments provided by the user

    """
    subcommands.build(args.copr, args.pkgs,
                      args.memory, args.timeout)


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
    subcommands.list(args.username)


def setup_parser():
    """
    Set the main arguments.
    """
    parser = argparse.ArgumentParser(prog="copr-cli")
    # General connection options
    parser.add_argument('--version', action='version',
                        version='copr-cli %s' % (__version__))

    subparsers = parser.add_subparsers(title='actions')

    # create the parser for the "list" command
    parser_list = subparsers.add_parser('list',
                                        help='List all the copr of the '
                                             'provided '
                                        )
    parser_list.add_argument("username", nargs='?',
                             help='The username that you would like to '
                             'list the copr of (defaults to current user)'
                             )
    parser_list.set_defaults(func=action_list)

    # create the parser for the "create" command
    parser_create = subparsers.add_parser('create',
                                          help='Create a new copr')
    parser_create.add_argument('name',
                               help='The name of the copr to create')
    parser_create.add_argument("--chroot", dest="chroots", action='append',
                               help="Chroot to use for this copr")
    parser_create.add_argument('--repo', dest='repos', action='append',
                               help="Repository to add to this copr")
    parser_create.add_argument('--initial-pkgs', dest='initial_pkgs',
                               action='append',
                               help="List of packages to build in this "
                                    "new copr")
    parser_create.add_argument('--description',
                               help="Description of the copr")
    parser_create.add_argument('--instructions',
                               help="Instructions for the copr")
    parser_create.set_defaults(func=action_create)

    # create the parser for the "build" command
    parser_build = subparsers.add_parser('build',
                                         help='Build packages to a '
                                         'specified copr')
    parser_build.add_argument('copr',
                              help='The copr repo to build the package in'
                              )
    parser_build.add_argument('pkgs', nargs='+', action='append')
    parser_build.add_argument('--memory', dest='memory',
                              help="")
    parser_build.add_argument('--timeout', dest='timeout',
                              help="")
    parser_build.set_defaults(func=action_build)

    return parser


def main(argv=sys.argv[1:]):
    """ Main function """
    try:
        # Set up parser for global args
        parser = setup_parser()
        # Parse the commandline
        arg = parser.parse_args()
        arg.func(arg)
    except KeyboardInterrupt:
        print "\nInterrupted by user."
        sys.exit(1)
    except argparse.ArgumentTypeError, e:
        print "\nError: {0}".format(e)
        sys.exit(2)
    except Exception, e:
        print 'Error: {0}'.format(e)
        sys.exit(100)


if __name__ == '__main__':
    main()
