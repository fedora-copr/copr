#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
import re
import subprocess

import argparse
from urlparse import urlparse
import sys
import datetime
import time
from collections import defaultdict

import logging

if sys.version_info < (2, 7):
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
else:
    from logging import NullHandler

log = logging.getLogger(__name__)
log.addHandler(NullHandler())

from copr import CoprClient
import copr.exceptions as copr_exceptions

from .util import ProgressBar


no_config_warning = """
|================ WARNING: =======================|
|File '~/.config/copr' is missing or incorrect.   |
| See documentation: man copr-cli.                |
| Any operation requiring credentionals will fail!|
|=================================================|

"""


class Commands(object):
    def __init__(self):

        try:
            self.client = CoprClient.create_from_file_config()
        except (copr_exceptions.CoprNoConfException,
                copr_exceptions.CoprConfigException):
            print(no_config_warning)
            self.client = CoprClient(
                copr_url=u"http://copr.fedoraproject.org",
                no_config=True
            )

    def requires_api_auth(func):
        """ Decorator that checks config presence
        """

        def wrapper(self, args):
            if self.client.no_config:
                print("Error: Operation requires api authentication\n"
                      "File `~/.config/copr` is missing or incorrect")
                sys.exit(6)

            return func(self, args)

        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        return wrapper

    def check_username_presence(func):
        """ Decorator that checks if username was provided
        """

        def wrapper(self, args):
            if self.client.no_config and args.username is None:
                print("Error: Operation requires username\n"
                      "Pass username to command or create `~/.config/copr`")
                sys.exit(6)

            if args.username is None and self.client.username is None:
                print("Error: Operation requires username\n"
                      "Pass username to command or add it to `~/.config/copr`")
                sys.exit(6)

            return func(self, args)

        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        return wrapper

    def _watch_builds(self, builds_list):
        """
         :param builds_list: list of BuildWrapper
         """
        print("Watching build(s): (this may be safely interrupted)")

        prevstatus = defaultdict(lambda: None)
        failed_ids = []

        watched = set([bw.build_id for bw in builds_list])
        done = set()

        try:
            while watched != done:
                for build_id in watched:
                    if build_id in done:
                        continue

                    build_details = self.client.get_build_details(build_id)

                    if build_details.output != "ok":
                        errmsg = "  Build {1}: Unable to get build status: {0}". \
                            format(build_details.error, build_id)
                        raise copr_exceptions.CoprRequestException(errmsg)

                    now = datetime.datetime.now()
                    if prevstatus[build_id] != build_details.status:
                        prevstatus[build_id] = build_details.status
                        print("  {0} Build {2}: {1}".format(
                            now.strftime("%H:%M:%S"),
                            build_details.status, build_id))

                    if build_details.status in ["failed"]:
                        failed_ids.append(build_id)
                    if build_details.status in ["succeeded", "skipped",
                                                "failed", "canceled"]:
                        done.add(build_id)
                    if build_details.status == "unknown":
                        raise copr_exceptions.CoprBuildException(
                            "Unknown status.")

                if watched == done:
                    break

                time.sleep(30)

            if failed_ids:
                raise copr_exceptions.CoprBuildException(
                    "Build(s) {0} failed.".format(
                        ", ".join(str(x) for x in failed_ids)))

        except KeyboardInterrupt:
            pass

    @requires_api_auth
    def action_build(self, args):
        """ Method called when the 'build' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """
        copr = args.copr
        m = re.match(r"([^/]+)/(.*)", copr)
        if m:
            username = m.group(1)
            copr = m.group(2)
        else:
            username = None

        if os.path.exists(args.pkgs[0]):
            bar = ProgressBar(max=os.path.getsize(args.pkgs[0]))

            def progress_callback(monitor):
                bar.next(n=8192)

            print('Uploading package {}'.format(args.pkgs[0]))
        else:
            progress_callback = None

        result = self.client.create_new_build(
            projectname=copr, chroots=args.chroots, pkgs=args.pkgs,
            memory=args.memory, timeout=args.timeout,
            username=username, progress_callback=progress_callback)

        bar.finish()

        if result.output != "ok":
            print(result.error)
            return
        print(result.message)

        build_ids = [bw.build_id for bw in result.builds_list]
        print("Created builds: {}".format(" ".join(map(str, build_ids))))

        if not args.nowait:
            self._watch_builds(result.builds_list)

    @requires_api_auth
    def action_create(self, args):
        """ Method called when the 'create' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """

        result = self.client.create_project(
            projectname=args.name, description=args.description,
            instructions=args.instructions, chroots=args.chroots,
            repos=args.repos, initial_pkgs=args.initial_pkgs)
        print(result.message)

    @requires_api_auth
    def action_modify_project(self, args):
        """ Method called when the 'modify' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """

        result = self.client.modify_project(
            projectname=args.name,
            description=args.description, instructions=args.instructions,
            repos=args.repos, disable_createrepo=args.disable_createrepo)

    @requires_api_auth
    def action_delete(self, args):
        """ Method called when the 'delete' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        result = self.client.delete_project(projectname=args.copr)
        print(result.message)

    @check_username_presence
    def action_list(self, args):
        """ Method called when the 'list' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """
        username = args.username or self.client.username
        result = self.client.get_projects_list(username)
        # import ipdb; ipdb.set_trace()
        if result.output != "ok":
            print(result.error)
            print("Un-expected data returned, please report this issue")
        elif not result.projects_list:
            print("No copr retrieved for user: '{0}'".format(username))
            return

        for prj in result.projects_list:
            print(prj)

    def action_status(self, args):
        result = self.client.get_build_details(args.build_id)
        print(result.status)

    def action_download_build(self, args):
        result = self.client.get_build_details(args.build_id)
        # TODO: can be simplified after https://bugzilla.redhat.com/show_bug.cgi?id=1133650
        #  and addition of that paths to api

        o = urlparse(result.src_pkg)
        pkgs_name = os.path.split(o.path)[-1]
        assert pkgs_name.endswith(".src.rpm")

        base_url = result.results
        base_len = len(os.path.split(base_url))

        pkg_dir = pkgs_name[:-8]
        for chroot, status in result.data["chroots"].items():
            if args.chroots and chroot not in args.chroots:
                continue

            cmd = "wget -r -nH --no-parent --reject 'index.html*'".split(' ')

            cmd.extend(['-P', os.path.join(args.dest, chroot)])
            cmd.extend(['--cut-dirs', str(base_len + 4)])
            cmd.append("{}{}/{}/".format(base_url, chroot, pkg_dir))

            subprocess.call(cmd)

    @requires_api_auth
    def action_cancel(self, args):
        """ Method called when the 'cancel' action has been selected by the
        user.
        :param args: argparse arguments provided by the user
        """
        result = self.client.cancel_build(args.build_id)
        print(result.status)


def setup_parser():
    """
    Set the main arguments.
    """
    parser = argparse.ArgumentParser(prog="copr")
    # General connection options

    parser.add_argument("--debug", dest="debug", action="store_true",
                        help="Enable debug output")

    subparsers = parser.add_subparsers(title="actions")

    # create the parser for the "list" command
    parser_list = subparsers.add_parser(
        "list",
        help="List all the copr of the "
             "provided "
    )
    parser_list.add_argument(
        "username", nargs="?",
        help="The username that you would like to "
             "list the copr of (defaults to current user)"
    )
    parser_list.set_defaults(func="action_list")

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
    parser_create.set_defaults(func="action_create")

    # create the parser for the "modify_project" command
    parser_modify = subparsers.add_parser("modify", help="Modify existing copr")

    parser_modify.add_argument("name", help="The name of the copr to modify")
    parser_modify.add_argument("--description",
                               help="Description of the copr")
    parser_modify.add_argument("--instructions",
                               help="Instructions for the copr")
    parser_modify.add_argument("--repo", dest="repos", action="append",
                               help="Repository to add to this copr")
    parser_modify.add_argument("--disable_createrepo",
                               help="Disable metadata auto generation")
    parser_modify.set_defaults(func="action_modify_project")

    # create the parser for the "delete" command
    parser_delete = subparsers.add_parser("delete",
                                          help="Deletes the entire project")
    parser_delete.add_argument("copr",
                               help="Name of your project to be deleted.")
    parser_delete.set_defaults(func="action_delete")

    # create the parser for the "build" command
    parser_build = subparsers.add_parser("build",
                                         help="Build packages to a "
                                              "specified copr")
    parser_build.add_argument(
        "copr",
        help="The copr repo to build the package in. Can just name of project or even in format username/project."
    )
    parser_build.add_argument("pkgs", nargs="+",
                              help="filename of SRPM or URL of packages to build")
    parser_build.add_argument(
        "-r", "--chroot", dest="chroots", action="append",
        help="If you don't need this build for all the project's chroots. You can use it several times for each"
             " chroot you need."
    )
    parser_build.add_argument("--memory", dest="memory",
                              help="")
    parser_build.add_argument("--timeout", dest="timeout",
                              help="")
    parser_build.add_argument("--nowait", action="store_true", default=False,
                              help="Don't wait for build")
    parser_build.set_defaults(func="action_build")

    # create the parser for the "status" command
    parser_status = subparsers.add_parser("status",
                                         help="Get build status of build"
                                              " specified by its ID")
    parser_status.add_argument("build_id",
                              help="Build ID")
    parser_status.set_defaults(func="action_status")

    # create the parser for the "download-build" command
    parser_download_build = subparsers.add_parser("download-build", help="Fetches built packages")
    parser_download_build.add_argument("build_id",
                              help="Build ID")
    parser_download_build.add_argument(
        "-r", "--chroot", dest="chroots", action="append",
        help="Select chroots to fetch"
    )
    parser_download_build.add_argument("--dest", "-d", dest="dest",
                              help="Base directory to store packages", default=".")

    parser_download_build.set_defaults(func="action_download_build")

    # create the parser for the "cancel" command
    parser_cancel = subparsers.add_parser("cancel",
                                         help="Cancel build specified by its ID")
    parser_cancel.add_argument("build_id",
                              help="Build ID")
    parser_cancel.set_defaults(func="action_cancel")

    return parser


def enable_debug():
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    log.debug("#  Debug log enabled  #")


def main(argv=sys.argv[1:]):
    try:
        # Set up parser for global args
        parser = setup_parser()
        # Parse the commandline
        arg = parser.parse_args(argv)
        if arg.debug:
            enable_debug()

        commands = Commands()
        getattr(commands, arg.func)(arg)

    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.")
        sys.exit(1)
    except copr_exceptions.CoprBuildException as e:
        sys.stderr.write("\nBuild error: {0}\n".format(e))
        sys.exit(4)
    except copr_exceptions.CoprUnknownResponseException as e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(5)
    except copr_exceptions.CoprRequestException as e:
        sys.stderr.write("\nSomething went wrong:")
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(1)
    except argparse.ArgumentTypeError as e:
        sys.stderr.write("\nError: {0}".format(e))
        sys.exit(2)
    except copr_exceptions.CoprException as e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(3)

        # except Exception as e:
        # print "Error: {0}".format(e)
        # sys.exit(100)


if __name__ == "__main__":
    main()
