# -*- coding: UTF-8 -*-

# pylint: disable=too-many-lines

import argparse
import datetime
import logging
import os
import re
import subprocess
import sys
import time
import warnings
from collections import defaultdict

import six
import pkg_resources
import requests

try:
    import argcomplete
except ImportError:
    argcomplete = None

from copr import CoprClient
import copr.exceptions as copr_exceptions
from copr.v3 import (
    Client, config_from_file, CoprException, CoprRequestException,
    CoprNoConfigException, CoprConfigException, CoprNoResultException,
)
from copr.v3.pagination import next_page
from .util import ProgressBar, json_dumps, serializable
from .build_config import MockProfile


if six.PY2:
    from urlparse import urljoin, urlparse
else:
    from urllib.parse import urljoin, urlparse

if sys.version_info < (2, 7):
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
else:
    from logging import NullHandler

log = logging.getLogger(__name__)
log.addHandler(NullHandler())


ON_OFF_MAP = {
    'on': True,
    'off': False,
    None: None,
}

BOOTSTRAP_MAP = {
    "default": "default",
    "on": "on",
    "off": "off",
    "image": "image",
    None: "default",
}

no_config_warning = """
================= WARNING: =======================
File '{0}' is missing or incorrect.
See documentation: man copr-cli.
Any operation requiring credentials will fail!
==================================================

Hint: {1}

"""

try:
    input = raw_input
except NameError:
    pass


class FrontendOutdatedCliException(Exception):
    """
    If Frontend is too old to process this cli request, error out with an
    informative text rather than some ugly traceback.

    :param minimal_version: string minimal copr-frontend version
    """
    def __init__(self, minimal_version):
        super(FrontendOutdatedCliException, self).__init__(
            "The Copr Frontend server you run against is older than {0}. "
            "Please contact the server administrator and request "
            "an update.".format(minimal_version)
        )


class ActionDeprecated(argparse.Action):
    """ automate deprecation warnings for options """
    def __call__(self, parser, namespace, values, option_string=None):
        options = ", ".join(self.option_strings)
        warnings.warn("Use of DEPRECATED option: {0}".format(options))
        # keep the normal "store" behavior
        setattr(namespace, self.dest, values)


def buildopts_from_args(args, progress_callback):
    """
    For all the build commands, parse the common set of build options.
    """
    buildopts = {
        "timeout": args.timeout,
        "chroots": args.chroots,
        "background": args.background,
        "progress_callback": progress_callback,
    }
    for opt in ["exclude_chroots", "bootstrap", "after_build_id", "with_build_id", "isolation"]:
        value = getattr(args, opt)
        if value is not None:
            buildopts[opt] = value
    return buildopts


class Commands(object):
    def __init__(self, config_path):
        self.config_path = config_path or '~/.config/copr'

        try:
            self.config = config_from_file(self.config_path)
        except (CoprNoConfigException, CoprConfigException) as ex:
            sys.stderr.write(no_config_warning.format(self.config_path, ex))
            self.config = {"copr_url": "http://copr.fedoraproject.org", "no_config": True}

        self.client = Client(self.config)

    def requires_api_auth(func):
        """ Decorator that checks config presence
        """

        def wrapper(self, args):
            if "no_config" in self.config:
                sys.stderr.write("Error: Operation requires api authentication\n")
                sys.exit(6)

            return func(self, args)

        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        return wrapper

    def check_username_presence(func):
        """ Decorator that checks if username was provided
        """

        def wrapper(self, args):
            if "no_config" in self.config and args.username is None:
                sys.stderr.write(
                    "Error: Operation requires username\n"
                    "Pass username to command or create `{0}`\n".format(self.config_path))
                sys.exit(6)

            if args.username is None and self.config["username"] is None:
                sys.stderr.write(
                    "Error: Operation requires username\n"
                    "Pass username to command or add it to `{0}`\n".format(self.config_path))
                sys.exit(6)

            return func(self, args)

        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        return wrapper

    def parse_name(self, name):
        m = re.match(r"([^/]+)/(.*)", name)
        if m:
            owner = m.group(1)
            name = m.group(2)
        else:
            owner = self.config["username"]
        return owner, name

    def parse_chroot_path(self, path):
        """
        Take a `path` in an `owner/project/chroot` format and return a tuple of
        the corresponding values, i.e. `(owner, project, chroot)`
        """
        m = re.match(r"(([^/]+)/)?([^/]+)/(.*)", path)
        if m:
            owner = m.group(2) or self.config["username"]
            return owner, m.group(3), m.group(4)
        raise CoprException("Unexpected chroot path format")

    def _watch_builds(self, build_ids):
        """
        :param build_ids: list of build IDs
        """
        print("Watching build(s): (this may be safely interrupted)")

        prevstatus = defaultdict(lambda: None)
        failed_ids = []

        watched = set(build_ids)
        done = set()

        try:
            while watched != done:
                for build_id in watched:
                    if build_id in done:
                        continue
                    try:
                        build_details = self.client.build_proxy.get(build_id=build_id)
                    except requests.ConnectionError as e:
                        raise CoprRequestException(e)
                    now = datetime.datetime.now()
                    if prevstatus[build_id] != build_details.state:
                        prevstatus[build_id] = build_details.state
                        print("  {0} Build {2}: {1}".format(
                            now.strftime("%H:%M:%S"),
                            build_details.state, build_id))
                        sys.stdout.flush()

                    if build_details.state in ["failed"]:
                        failed_ids.append(build_id)
                    if build_details.state in ["succeeded", "skipped",
                                               "failed", "canceled"]:
                        done.add(build_id)
                    if build_details.state == "unknown":
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

    def action_whoami(self, args):
        """
        Simply print out the current user as defined in copr config.
        """
        print(self.config["username"])

    def action_new_webhook_secret(self, args):
        """
        Regenerate webhook secret for a copr.
        """
        answer = None

        while not answer:
            a = input('Generate a new webhook secret for {0} [y/n]? '.format(args.name))

            if a == 'n' or a == 'no':
                answer = 'n'
            if a == 'y' or a == 'yes':
                answer = 'y'

        if answer == 'y':
            ownername, projectname = self.parse_name(args.name)

            # @TODO Rewrite this call to the APIv3.
            # @TODO I am not doing it right away because it is a release-blocker
            # @TODO and I don't have a time to do it right now.
            client = CoprClient.create_from_file_config()
            result = client.new_webhook_secret(projectname, ownername=ownername)

            if result.output != "ok":
                sys.stderr.write(result.error + "\n")
                sys.stderr.write("Un-expected data returned, please report this issue\n")

            print(result.message)

    @requires_api_auth
    def action_build(self, args):
        """ Method called when the 'build' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        self.client.build_proxy.auth_check()

        builds = []
        for pkg in args.pkgs:
            if os.path.exists(pkg):
                bar = ProgressBar(max=os.path.getsize(pkg))
                build_function = self.client.build_proxy.create_from_file
                data = {"path": pkg}

                # pylint: disable=function-redefined
                def progress_callback(monitor):
                    bar.next(n=8192)

                print('Uploading package {0}'.format(pkg))
            elif not urlparse(pkg).scheme:
                raise CoprException("File {0} not found".format(pkg))
            else:
                bar = None
                progress_callback = None
                build_function = self.client.build_proxy.create_from_url
                data = {"url": pkg}

            builds.append(self.process_build(args, build_function, data, bar=bar, progress_callback=progress_callback))

        return builds

    @requires_api_auth
    def action_build_pypi(self, args):
        """
        Method called when the 'buildpypi' action has been selected by the user.

        :param args: argparse arguments provided by the user
        """
        data = {
            "pypi_package_name": args.packagename,
            "pypi_package_version": args.packageversion,
            "spec_template": args.spec_template,
            "python_versions": args.pythonversions,
        }
        return self.process_build(args, self.client.build_proxy.create_from_pypi, data)

    @requires_api_auth
    def action_build_scm(self, args):
        """
        Method called when the 'buildscm' action has been selected by the user.

        :param args: argparse arguments provided by the user
        """
        data = {
            "clone_url": args.clone_url,
            "committish": args.committish,
            "subdirectory": args.subdirectory,
            "spec": args.spec,
            "scm_type": args.scm_type,
            "source_build_method": args.srpm_build_method,
        }
        return self.process_build(args, self.client.build_proxy.create_from_scm, data)

    @requires_api_auth
    def action_build_distgit_simple(self, args):
        """ build-distgit method """
        data = {
            "packagename": args.pkgname,
            "distgit": args.instance,
            "namespace": args.namespace,
            "committish": args.committish,
        }
        return self.process_build(
            args, self.client.build_proxy.create_from_distgit, data)

    @requires_api_auth
    def action_build_rubygems(self, args):
        """
        Method called when the 'buildgem' action has been selected by the user.

        :param args: argparse arguments provided by the user
        """
        data = {"gem_name": args.gem_name}
        return self.process_build(args, self.client.build_proxy.create_from_rubygems, data)

    @requires_api_auth
    def action_build_custom(self, args):
        """
        Method called when 'buildcustom' has been selected by the user.

        :param args: argparse arguments provided by the user
        """
        data = {
            'script': ''.join(args.script.readlines()),
        }
        for arg in ['script_chroot', 'script_builddeps',
                    'script_resultdir']:
            data[arg] = getattr(args, arg)
        return self.process_build(args, self.client.build_proxy.create_from_custom, data)

    @requires_api_auth
    def action_build_distgit(self, args):
        """
        Method called when the 'buildfedpkg' action has been selected by the user.

        :param args: argparse arguments provided by the user
        """
        data = {"clone_url": args.clone_url, "committish": args.branch}
        return self.process_build(args, self.client.build_proxy.create_from_scm, data)

    def process_build(self, args, build_function, data, bar=None, progress_callback=None):
        username, project_dirname = self.parse_name(args.copr_repo)
        projectname = project_dirname.split(':')[0]

        try:
            buildopts = buildopts_from_args(args, progress_callback)
            result = build_function(ownername=username, projectname=projectname,
                                    project_dirname=project_dirname, buildopts=buildopts, **data)

            builds = result if type(result) == list else [result]
            print("Build was added to {0}:".format(builds[0].projectname))

            for build in builds:
                url = urljoin(self.config["copr_url"], "/coprs/build/{0}".format(build.id))
                print("  {0}".format(url))

            build_ids = [build.id for build in builds]
            print("Created builds: {0}".format(" ".join(map(str, build_ids))))

            if not args.nowait:
                self._watch_builds(build_ids)

        except CoprException as ex:
            sys.stderr.write(str(ex) + "\n")
            sys.exit(1)
        finally:
            if bar:
                bar.finish()


    @requires_api_auth
    def action_create(self, args):
        """ Method called when the 'create' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """
        username, copr = self.parse_name(args.name)
        project = self.client.project_proxy.add(
            ownername=username, projectname=copr, description=args.description,
            instructions=args.instructions, chroots=args.chroots,
            additional_repos=args.repos, # packages=args.initial_pkgs, @TODO remove packages
            devel_mode=args.disable_createrepo,
            unlisted_on_hp=ON_OFF_MAP[args.unlisted_on_hp],
            enable_net=ON_OFF_MAP[args.enable_net],
            persistent=args.persistent,
            auto_prune=ON_OFF_MAP[args.auto_prune],
            bootstrap=BOOTSTRAP_MAP[args.bootstrap],
            isolation=args.isolation,
            delete_after_days=args.delete_after_days,
            multilib=ON_OFF_MAP[args.multilib],
            module_hotfixes=ON_OFF_MAP[args.module_hotfixes],
        )
        print("New project was successfully created.")

    @requires_api_auth
    def action_modify_project(self, args):
        """ Method called when the 'modify' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        username, copr = self.parse_name(args.name)
        project = self.client.project_proxy.edit(
            ownername=username, projectname=copr,
            description=args.description, instructions=args.instructions,
            additional_repos=args.repos, devel_mode=args.disable_createrepo,
            unlisted_on_hp=ON_OFF_MAP[args.unlisted_on_hp],
            enable_net=ON_OFF_MAP[args.enable_net],
            auto_prune=ON_OFF_MAP[args.auto_prune],
            bootstrap=BOOTSTRAP_MAP[args.bootstrap],
            isolation=args.isolation,
            chroots=args.chroots,
            delete_after_days=args.delete_after_days,
            multilib=ON_OFF_MAP[args.multilib],
            module_hotfixes=ON_OFF_MAP[args.module_hotfixes],
        )

    @requires_api_auth
    def action_delete(self, args):
        """ Method called when the 'delete' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        username, copr = self.parse_name(args.copr)
        project = self.client.project_proxy.delete(ownername=username, projectname=copr)
        print("Project {0} has been deleted.".format(project.name))

    @requires_api_auth
    def action_fork(self, args):
        """ Method called when the 'fork' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        srcownername, srcprojectname = self.parse_name(args.src)
        dstownername, dstprojectname = self.parse_name(args.dst)

        try:
            dst = self.client.project_proxy.get(ownername=dstownername, projectname=dstprojectname)
        except CoprNoResultException:
            dst = None

        project = self.client.project_proxy.fork(ownername=srcownername, projectname=srcprojectname,
                                                 dstownername=dstownername, dstprojectname=dstprojectname,
                                                 confirm=args.confirm)
        if not dst:
            print("Forking project {0}/{1} for you into {2}.\nPlease be aware that it may take a few minutes "
                  "to duplicate backend data.".format(srcownername, srcprojectname, project.full_name))
        else:
            print("Updating packages in {0} from {1}/{2}.\nPlease be aware that it may take a few minutes "
                  "to duplicate backend data.".format(project.full_name, srcownername, srcprojectname))

    def action_list_builds(self, args):
        """ Method called when the 'list-builds' action has been selected by
        the user.

        :param args: argparse arguments provided by the user
        """
        ownername, projectname = self.parse_name(args.project)
        pagination = {"limit": 100}

        builds_list = self.client.build_proxy.get_list(ownername, projectname,
                                                       pagination=pagination)
        while builds_list:
            for build in builds_list:
                print("{0}\t{1}\t{2}".format(build["id"], build["source_package"]["name"],
                                             build["state"]))
            builds_list = next_page(builds_list)

    def action_mock_config(self, args):
        """ Method called when the 'mock-config' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """
        ownername, projectname = self.parse_name(args.project)
        build_config = self.client.project_chroot_proxy.get_build_config(ownername, projectname, args.chroot)
        build_config.rootdir = "{0}-{1}_{2}".format(ownername.replace("@", "group_"), projectname, args.chroot)
        print(MockProfile(build_config))


    @check_username_presence
    def action_list(self, args):
        """ Method called when the 'list' action has been selected by the
        user.

        :param args: argparse arguments provided by the user

        """
        username = args.username or self.config["username"]
        try:
            projects = self.client.project_proxy.get_list(username)
            if not projects:
                sys.stderr.write("No copr retrieved for user: '{0}'\n".format(username))
                return

            for project in projects:
                print("Name: {0}".format(project.name))
                print("  Description: {0}".format(project.description))
                if project.chroot_repos:
                    print("  Repo(s):")
                    for name, url in project.chroot_repos.items():
                        print("    {0}: {1}".format(name, url))
                if project.additional_repos:
                    print("  Additional repo: {0}".format(" ".join(project.additional_repos)))
                print("")

        except CoprRequestException as ex:
            sys.stderr.write(str(ex) + "\n")
            sys.stderr.write("Un-expected data returned, please report this issue\n")

    def action_status(self, args):
        build = self.client.build_proxy.get(args.build_id)
        print(build.state)

    def action_download_build(self, args):
        build = self.client.build_proxy.get(args.build_id)
        base_len = len(os.path.split(build.repo_url))
        build_chroots = self.client.build_chroot_proxy.get_list(args.build_id)

        for chroot in build_chroots:
            if args.chroots and chroot.name not in args.chroots:
                continue

            if not chroot.result_url:
                sys.stderr.write("No data for build id: {} and chroot: {}.\n".format(args.build_id, chroot.name))
                continue

            cmd = ['wget', '-r', '-nH', '--no-parent', '--reject', '"index.html*"', '-e', 'robots=off', '--no-verbose']
            cmd.extend(['-P', os.path.join(args.dest, chroot.name)])
            cmd.extend(['--cut-dirs', str(base_len + 4)])
            cmd.append(chroot.result_url)
            subprocess.call(cmd)

    @requires_api_auth
    def action_cancel(self, args):
        """ Method called when the 'cancel' action has been selected by the
        user.
        :param args: argparse arguments provided by the user
        """
        build = self.client.build_proxy.cancel(args.build_id)
        print(build.state)

    def action_watch_build(self, args):
        self._watch_builds(args.build_id)

    def action_delete_build(self, args):
        result = self.client.build_proxy.delete_list(args.build_id)
        print("Build(s) {0} were deleted.".format(", ".join(map(str, result["builds"]))))

    #########################################################
    ###                   Chroot actions                  ###
    #########################################################

    @requires_api_auth
    def action_edit_chroot(self, args):
        """ Method called when the 'edit-chroot' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """

        if args.bootstrap_image:
            args.bootstrap = 'image'
        owner, copr, chroot = self.parse_chroot_path(args.coprchroot)
        self.client.project_chroot_proxy.edit(
            ownername=owner, projectname=copr, chrootname=chroot,
            comps=args.upload_comps, delete_comps=args.delete_comps,
            additional_packages=args.packages, additional_repos=args.repos,
            bootstrap=args.bootstrap, bootstrap_image=args.bootstrap_image,
            isolation=args.isolation,
        )
        print("Edit chroot operation was successful.")

    def action_get_chroot(self, args):
        """ Method called when the 'get-chroot' action has been selected by the
        user.

        :param args: argparse arguments provided by the user
        """
        owner, copr, chroot = self.parse_chroot_path(args.coprchroot)
        project_chroot = self.client.project_chroot_proxy.get(
            ownername=owner, projectname=copr, chrootname=chroot
        )
        print(json_dumps(project_chroot))

    def action_list_chroots(self, args):
        """List all currently available chroots.
        """
        def indent(string):
            return '\n'.join(['    ' + l for l in string.split('\n')])

        chroots = self.client.mock_chroot_proxy.get_list()
        chroots = serializable(chroots)
        for chroot, comment in chroots.items():
            print(chroot)
            if comment:
                print(indent(comment))

    #########################################################
    ###                   Package actions                 ###
    #########################################################

    @requires_api_auth
    def action_add_or_edit_package_pypi(self, args):
        ownername, projectname = self.parse_name(args.copr)
        data = {
            "package_name": args.name,
            "pypi_package_name": args.packagename,
            "pypi_package_version": args.packageversion,
            "spec_template": args.spec_template,
            "python_versions": args.pythonversions,
            "max_builds": args.max_builds,
            "webhook_rebuild": ON_OFF_MAP[args.webhook_rebuild],
        }
        if args.create:
            package = self.client.package_proxy.add(ownername, projectname, args.name, "pypi", data)
        else:
            package = self.client.package_proxy.edit(ownername, projectname, args.name, "pypi", data)
        print("Create or edit operation was successful.")

    @requires_api_auth
    def action_add_or_edit_package_scm(self, args):
        ownername, projectname = self.parse_name(args.copr)
        data = {
            "package_name": args.name,
            "clone_url": args.clone_url,
            "committish": args.committish,
            "subdirectory": args.subdirectory,
            "spec": args.spec,
            "scm_type": args.scm_type,
            "source_build_method": args.srpm_build_method,
            "max_builds": args.max_builds,
            "webhook_rebuild": ON_OFF_MAP[args.webhook_rebuild],
        }
        if args.create:
            package = self.client.package_proxy.add(ownername, projectname, args.name, "scm", data)
        else:
            package = self.client.package_proxy.edit(ownername, projectname, args.name, "scm", data)
        print("Create or edit operation was successful.")

    @requires_api_auth
    def action_add_or_edit_package_distgit(self, args):
        """ process 'add/edit-package-distgit' requests """
        data = {
            # package name (args.name) is not needed in data
            "distgit": args.instance,
            "namespace": args.namespace,
            "committish": args.committish,
            "max_builds": args.max_builds,
            "webhook_rebuild": ON_OFF_MAP[args.webhook_rebuild],
        }
        ownername, projectname = self.parse_name(args.copr)
        if args.create:
            self.client.package_proxy.add(ownername, projectname, args.name,
                                          "distgit", data)
        else:
            self.client.package_proxy.edit(ownername, projectname, args.name,
                                           "distgit", data)
        print("Create or edit operation was successful.")

    @requires_api_auth
    def action_add_or_edit_package_rubygems(self, args):
        ownername, projectname = self.parse_name(args.copr)
        data = {
            "package_name": args.name,
            "gem_name": args.gem_name,
            "max_builds": args.max_builds,
            "webhook_rebuild": ON_OFF_MAP[args.webhook_rebuild],
        }
        if args.create:
            package = self.client.package_proxy.add(ownername, projectname, args.name, "rubygems", data)
        else:
            package = self.client.package_proxy.edit(ownername, projectname, args.name, "rubygems", data)
        print("Create or edit operation was successful.")

    @requires_api_auth
    def action_add_or_edit_package_custom(self, args):
        ownername, projectname = self.parse_name(args.copr)
        data = {
            "package_name": args.name,
            "script": ''.join(args.script.readlines()),
            "script_chroot": args.script_chroot,
            "script_builddeps": args.script_builddeps,
            "script_resultdir": args.script_resultdir,
            "max_builds": args.max_builds,
            "webhook_rebuild": ON_OFF_MAP[args.webhook_rebuild],
        }
        if args.create:
            package = self.client.package_proxy.add(ownername, projectname, args.name, "custom", data)
        else:
            package = self.client.package_proxy.edit(ownername, projectname, args.name, "custom", data)
        print("Create or edit operation was successful.")

    def action_list_packages(self, args):
        ownername, projectname = self.parse_name(args.copr)
        packages = self.client.package_proxy.get_list(ownername=ownername, projectname=projectname,
                                                      with_latest_build=args.with_latest_build,
                                                      with_latest_succeeded_build=args.with_latest_succeeded_build)
        packages_with_builds = [self._package_with_builds(p, args) for p in packages]
        print(json_dumps(packages_with_builds))

    def action_list_package_names(self, args):
        ownername, projectname = self.parse_name(args.copr)
        packages = self.client.package_proxy.get_list(ownername=ownername, projectname=projectname)
        for package in packages:
            print(package.name)

    def action_get_package(self, args):
        ownername, projectname = self.parse_name(args.copr)
        package = self.client.package_proxy.get(
            ownername=ownername,
            projectname=projectname,
            packagename=args.name,
            with_latest_build=args.with_latest_build,
            with_latest_succeeded_build=args.with_latest_succeeded_build,
        )
        package = self._package_with_builds(package, args)
        print(json_dumps(package))

    def _package_with_builds(self, package, args):
        ownername, projectname = self.parse_name(args.copr)
        kwargs = {"ownername": ownername, "projectname": projectname, "packagename": package.name}

        # Avoid raising a KeyError here
        if not "builds" in package:
            raise FrontendOutdatedCliException("1.167")

        # Keep output of copr-cli compatible with copr-cli <= 1.87.
        api_provided_builds = package["builds"]
        del package["builds"]
        for key in ["latest_succeeded", "latest"]:
            if key in api_provided_builds:
                package[key + "_build"] = api_provided_builds[key]

        if args.with_all_builds:
            builds = self.client.build_proxy.get_list(**kwargs)
            package["builds"] = builds

        return package

    def action_delete_package(self, args):
        ownername, projectname = self.parse_name(args.copr)
        package = self.client.package_proxy.delete(ownername=ownername, projectname=projectname, packagename=args.name)
        print("Package {0} was successfully deleted.".format(args.name))

    def action_reset_package(self, args):
        ownername, projectname = self.parse_name(args.copr)
        package = self.client.package_proxy.reset(ownername=ownername, projectname=projectname, packagename=args.name)
        print("Package's default source was successfully reseted.")

    def action_build_package(self, args):
        ownername, project_dirname = self.parse_name(args.copr_repo)
        projectname = project_dirname.split(':')[0]
        buildopts = buildopts_from_args(args, None)
        try:
            build = self.client.package_proxy.build(ownername=ownername, projectname=projectname,
                                                    packagename=args.name, buildopts=buildopts,
                                                    project_dirname=project_dirname)
            print("Build was added to {0}.".format(build.projectname))
            print("Created builds: {0}".format(build.id))

            if not args.nowait:
                self._watch_builds([build.id])
        except CoprRequestException as ex:
            sys.stderr.write(str(ex) + "\n")

    def action_build_module(self, args):
        """
        Build module via Copr MBS
        """
        ownername, projectname = self.parse_name(args.copr)

        if args.yaml:
            try:
                module = self.client.module_proxy.build_from_file(
                        ownername, projectname, args.yaml, distgit=args.distgit)
            except FileNotFoundError as e:
                raise CoprRequestException("File '{filename}' not found".format(filename=e.filename))
        else:
            module = self.client.module_proxy.build_from_url(
                    ownername, projectname, args.url, distgit=args.distgit)
        print("Created module {0}".format(module.nsv))

    def action_permissions_edit(self, args):
        ownername, projectname = self.parse_name(args.project)
        if not args.permissions:
            raise argparse.ArgumentTypeError(
                "neither --builder nor --admin specified")
        self.client.project_proxy.set_permissions(ownername, projectname,
                args.permissions)
        print("success")

    def action_permissions_list(self, args):
        ownername, projectname = self.parse_name(args.project)
        perms = self.client.project_proxy.get_permissions(ownername, projectname)
        for user in perms['permissions']:
            print(user + ":")
            for role, value in perms['permissions'][user].items():
                print("  {0}: {1}".format(role, value))

    def action_permissions_request(self, args):
        if not args.permissions:
            raise argparse.ArgumentTypeError(
                "neither --builder nor --admin specified")
        ownername, projectname = self.parse_name(args.project)
        request = {}
        for role, value in args.permissions['your user'].items():
            if value == 'nothing':
                request[role] = False
            elif value == 'request':
                request[role] = True
            else:
                raise argparse.ArgumentTypeError(
                        "--{0} can be 'nothing' or 'request', "
                        "not '{1}'".format(role, value))
        self.client.project_proxy.request_permissions(ownername, projectname,
                                                      request)
        print("success")

def setup_parser():
    """
    Set the main arguments.
    """
    #########################################################
    ###                    General options                ###
    #########################################################

    parser = argparse.ArgumentParser(prog="copr")
    # General connection options

    parser.add_argument("--debug", dest="debug", action="store_true",
                        help="Enable debug output")

    parser.add_argument("--config", dest="config",
                        help="Path to an alternative configuration file")

    parser.add_argument("--version", action="version",
                        version="%(prog)s version " + pkg_resources.require('copr-cli')[0].version)

    subparsers = parser.add_subparsers(title="actions")

    #########################################################
    ###                    Project options                ###
    #########################################################

    parser_whoami = subparsers.add_parser(
        "whoami",
        help="Print username that the client authenticates with against copr-frontend")
    parser_whoami.set_defaults(func="action_whoami")

    parser_new_webhook_secret = subparsers.add_parser(
        "new-webhook-secret",
        help="Regenerate webhoook secret for a copr.")
    parser_new_webhook_secret.add_argument("name", help="copr to generate a new webhook secret for.")
    parser_new_webhook_secret.set_defaults(func="action_new_webhook_secret")

    # create the parser for the "list" command
    parser_list = subparsers.add_parser(
        "list",
        help="List all the copr of the "
             "provided "
    )
    parser_list.add_argument(
        "username", metavar="username|@groupname", nargs="?",
        help="The username or @groupname that you would like to "
             "list the coprs of (defaults to current user)"
    )
    parser_list.set_defaults(func="action_list")

    parser_mock_config = subparsers.add_parser(
        "mock-config",
        help="Get the mock profile (similar to koji mock-config)"
    )
    parser_mock_config.add_argument(
        "project",
        help="Expected format is <user>/<project>, <group>/<project> (including '@') or <project> (name of project you own)."
    )
    parser_mock_config.add_argument(
        "chroot",
        help="chroot id, e.g. 'fedora-rawhide-x86_64'"
    )
    parser_mock_config.set_defaults(func="action_mock_config")

    # create the parser for the "create" command
    parser_create = subparsers.add_parser("create", help="Create a new copr")
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
    parser_create.add_argument("--disable_createrepo", type=str2bool,
                               help="Disable metadata auto generation")
    parser_create.add_argument("--enable-net", choices=["on", "off"], default="off",
                               help="If net should be enabled for builds in this project (default is off)")
    parser_create.add_argument("--unlisted-on-hp", choices=["on", "off"],
                               help="The project will not be shown on COPR home page")
    parser_create.add_argument("--persistent", action="store_true",
                               help="Project and its builds will be undeletable. This option can only be specified by a COPR admin.")
    parser_create.add_argument("--auto-prune", choices=["on", "off"], default="on",
                               help="If auto-deletion of project's obsoleted builds should be enabled (default is on).\
                               This option can only be specified by a COPR admin.")
    parser_create.add_argument("--isolation", choices=["simple", "nspawn", "default"], default="default",
                               help="Choose the isolation method for running commands in buildroot.")

    parser_create.add_argument(
        "--bootstrap",
        choices=["default", "on", "off", "image"],
        help=(
            "Configure Mock's bootstrap feature (consult 'man mock' for more "
            "info).  'on'/'off' enables/disables bootstrap.  The 'default' "
            "variant uses pre-configured setup from mock-core-configs.  The "
            "'image' variant enforces the bootstrap initialization from "
            "the pre-configured container image (defined in "
            "mock-core-configs.rpm)."
        ),
    )

    parser_create.add_argument("--delete-after-days", default=None, metavar='DAYS',
                               help="Delete the project after the specfied period of time")
    parser_create.add_argument("--module-hotfixes", choices=["on", "off"], default="off",
                               help=("make packages from this project available "
                                     "on along with packages from the active module streams."))
    parser_create.add_argument(
        "--multilib", choices=["on", "off"], default="off",
        help=("When users enable this copr repository on 64bit variant of "
              "multilib capable architecture (e.g. x86_64), they will also be "
              "able to install 32bit variants of the packages (e.g. i386 for "
              "x86_64 arch), default is 'off'"))

    parser_create.set_defaults(func="action_create")

    # create the parser for the "modify_project" command
    parser_modify = subparsers.add_parser("modify", help="Modify existing copr")

    parser_modify.add_argument("name", help="The name of the copr to modify")
    parser_modify.add_argument("--chroot", dest="chroots", action="append",
                               help="Chroot to use for this copr")
    parser_modify.add_argument("--description",
                               help="Description of the copr")
    parser_modify.add_argument("--instructions",
                               help="Instructions for the copr")
    parser_modify.add_argument("--repo", dest="repos", action="append",
                               help="Repository to add to this copr")
    parser_modify.add_argument("--disable_createrepo", type=str2bool,
                               help="Disable metadata auto generation")
    parser_modify.add_argument("--enable-net", choices=["on", "off"],
                               help="If net should be enabled for builds in this project (default is \"don't change\")")
    parser_modify.add_argument("--unlisted-on-hp", choices=["on", "off"],
                               help="The project will not be shown on COPR home page")
    parser_modify.add_argument("--auto-prune", choices=["on", "off"],
                               help="If auto-deletion of project's obsoleted builds should be enabled.\
                               This option can only be specified by a COPR admin.")
    parser_modify.add_argument("--isolation", choices=["simple", "nspawn", "default"],
                               help="Choose the isolation method for running commands in buildroot.")

    parser_modify.add_argument(
        "--bootstrap",
        choices=["default", "on", "off", "image"],
        help=("Configure Mock's bootstrap feature, "
              "See 'create --help' for more info."))

    parser_modify.add_argument("--delete-after-days", default=None, metavar='DAYS',
                               help=("Delete the project after the specfied "
                                     "period of time, empty or -1 disables, "
                                     "(default is \"don't change\")"))
    parser_modify.add_argument("--module-hotfixes", choices=["on", "off"],
                               help=("make packages from this project available "
                                     "on along with packages from the active module streams."))
    parser_modify.add_argument(
        "--multilib", choices=["on", "off"],
        help=("When users enable this copr repository on 64bit variant of "
              "multilib capable architecture (e.g. x86_64), they will also be "
              "able to install 32bit variants of the packages (e.g. i386 for "
              "x86_64 arch), default is \"don't change\""))
    parser_modify.set_defaults(func="action_modify_project")

    # create the parser for the "delete" command
    parser_delete = subparsers.add_parser("delete", help="Deletes the entire project")
    parser_delete.add_argument("copr", help="Name of your project to be deleted.")
    parser_delete.set_defaults(func="action_delete")

    # create the parser for the "fork" command
    parser_delete = subparsers.add_parser("fork", help="Fork the project and builds in it")
    parser_delete.add_argument("src", help="Which project should be forked")
    parser_delete.add_argument("dst", help="Name of the new project")
    parser_delete.add_argument("--confirm", action="store_true", help="Confirm forking into existing project")
    parser_delete.set_defaults(func="action_fork")

    parser_builds = subparsers.add_parser("list-builds", help="List all builds in the project")
    parser_builds.add_argument("project", help="Which project's builds should be listed.\
                               Can be just a name of the project or even in format\
                               username/project or @groupname/project.")
    parser_builds.set_defaults(func="action_list_builds")

    #########################################################
    ###             Source-type related options           ###
    #########################################################

    parser_pypi_args_optional = argparse.ArgumentParser(add_help=False)
    parser_pypi_args_optional.add_argument("--pythonversions", nargs="*", type=int, metavar="VERSION",
                                         help="For what Python versions to build (by default: 3 2)")
    parser_pypi_args_optional.add_argument("--packageversion", metavar = "PYPIVERSION",
                                         help="Version of the PyPI package to be built (by default latest)")
    parser_pypi_args_optional.add_argument("--template", "-t", dest="spec_template",
                                         help="Spec template to be used to build srpm with pyp2rpm")

    parser_pypi_args_parent = argparse.ArgumentParser(add_help=False, parents=[parser_pypi_args_optional])
    parser_pypi_args_parent.add_argument("--packagename", required=True, metavar="PYPINAME",
                                         help="Name of the PyPI package to be built, required.")

    parser_scm_args_parent = argparse.ArgumentParser(add_help=False)
    parser_scm_args_parent.add_argument("--clone-url", required=True,
                                        help="clone url to a project versioned by Git or SVN, required")
    parser_scm_args_parent.add_argument("--commit", dest="committish", default="",
                                        help="branch name, tag name, or git hash to be built")
    parser_scm_args_parent.add_argument("--subdir", dest="subdirectory", default="",
                                        help="relative path from the repo root to the package content")
    parser_scm_args_parent.add_argument("--spec", default="",
                                        help="relative path from the subdirectory to the .spec file")
    parser_scm_args_parent.add_argument("--type", dest="scm_type", choices=["git", "svn"], default="git",
                                        help="Specify versioning tool. Default is 'git'.")
    parser_scm_args_parent.add_argument("--method", dest="srpm_build_method", default="rpkg",
                                        choices=["rpkg", "tito", "tito_test", "make_srpm"],
                                        help="Srpm build method. Default is 'rpkg'.")

    parser_distgit_simple_parent = argparse.ArgumentParser(add_help=False)
    parser_distgit_simple_parent.add_argument(
        "--commit", dest="committish", default=None,
        help="Branch name, tag name, or git hash to built the package from")
    parser_distgit_simple_parent.add_argument(
        "--namespace", dest="namespace", default=None,
        help=(
            "Some DistGit instances (e.g. the Fedora Copr dist-git) use "
            "a namespaced clone/lookaside URLs.  Typically it meas that "
            "one package may be hosted in the same DistGit instance "
            "multiple times, in multiple namespaces.  Specify the NAMESPACE "
            "here (e.g. @copr/copr for @copr/copr/copr-cli package)."),
    )
    parser_distgit_simple_parent.add_argument(
        "--distgit", dest="instance", default=None,
        help=(
            "Dist-git instance to build the package from, for example "
            "'fedora'."
        ),
    )

    parser_rubygems_args_parent = argparse.ArgumentParser(add_help=False)
    parser_rubygems_args_parent.add_argument("--gem", metavar="GEM", dest="gem_name",
                                             help="Specify gem name")

    parser_distgit_args_parent = argparse.ArgumentParser(add_help=False)
    parser_distgit_args_parent.add_argument("--clone-url", metavar="URL", dest="clone_url", required=True,
                                             help="Specify clone url for the distgit repository")
    parser_distgit_args_parent.add_argument("--branch", metavar="BRANCH", dest="branch",
                                             help="Specify branch to be used")

    parser_custom_args_parent = argparse.ArgumentParser(add_help=False)
    parser_custom_args_parent.add_argument(
            '--script', required=True,
            type=argparse.FileType('r'),
            help='text file (script) to be used to prepare the sources')
    parser_custom_args_parent.add_argument(
            '--script-chroot',
            help='mock chroot to build sources for the SRPM in')
    parser_custom_args_parent.add_argument(
            '--script-builddeps',
            type=lambda x: x.split(),  # Store the deps as a list
            help='space separated list of packages needed to build the sources')
    parser_custom_args_parent.add_argument(
            '--script-resultdir',
            help='where SCRIPT generates the result, relatively to script\'s '
                 '$PWD (defaults to \'.\')')

    #########################################################
    ###                    Build options                  ###
    #########################################################

    # parent parser for the builds commands below
    parser_build_parent = argparse.ArgumentParser(add_help=False)
    parser_build_parent.add_argument("copr_repo",
                                     help="The copr repo to build the package in. Can be just name of project or even in format username/project or @groupname/project. "
                                     "It can also be in the form project:<tag>, which will put the build into a side repository with the user-chosen tag in its name.")
    parser_build_parent.add_argument("--memory", dest="memory",
                                     help=argparse.SUPPRESS,
                                     action=ActionDeprecated)
    parser_build_parent.add_argument(
        "--timeout", dest="timeout",
        help=("Specify build timeout (seconds), if the build takes "
              "longer than that, it is terminated and fails.  The "
              "default is usually set to 5 hours on Copr Frontend."))
    parser_build_parent.add_argument("--nowait", action="store_true", default=False,
                                     help="Don't wait for build")
    parser_build_parent.add_argument("-r", "--chroot", dest="chroots", action="append",
                                     help="If you don't need this build for all the project's chroots. You can use it several times for each chroot you need.")

    parser_build_parent.add_argument(
        "--exclude-chroot",
        dest="exclude_chroots",
        action="append",
        help=("If you don't need this build for all the project's chroots."
              "You can use it several times for each chroot you don't need.")
    )

    parser_build_parent.add_argument("--background", dest="background", action="store_true", default=False,
                                     help="Mark the build as a background job. It will have lesser priority than regular builds.")
    parser_build_parent.add_argument("--isolation", choices=["simple", "nspawn", "default"], default="unchanged",
                                     help="Choose the isolation method for running commands in buildroot.")

    parser_build_parent.add_argument(
        "--bootstrap",
        choices=["unchanged", "default", "on", "off", "image"],
        help=("Configure Mock's bootstrap feature, "
              "default is 'unchanged' so the configuration from Copr project "
              "and Copr chroot is used for this build. "
              "The 'default' variant resets the project/chroot configuration "
              "to the pre-configured setup from mock-core-configs. "
              "See 'create --help' for more info."))

    batch_build_opts = parser_build_parent.add_mutually_exclusive_group()
    batch_build_opts.add_argument(
        "--after-build-id", metavar="BUILD_ID",
        help=("Build after the batch containing the BUILD_ID build."),
    )

    batch_build_opts.add_argument(
        "--with-build-id", metavar="BUILD_ID",
        help=("Build in the same batch with the BUILD_ID build."),
    )

    # create the parser for the "build" (url/upload) command
    parser_build = subparsers.add_parser("build", parents=[parser_build_parent],
                                         help="Build packages to a specified copr")
    parser_build.add_argument("pkgs", nargs="+",
                              help="filename of SRPM or URL of packages to build")

    parser_build.set_defaults(func="action_build")

    # create the parser for the "buildpypi" command
    parser_build_pypi = subparsers.add_parser("buildpypi", parents=[parser_pypi_args_parent, parser_build_parent],
                                              help="Build PyPI package to a specified copr")
    parser_build_pypi.set_defaults(func="action_build_pypi")

    # create the parser for the "buildgem" command
    parser_build_rubygems = subparsers.add_parser("buildgem", parents=[parser_rubygems_args_parent, parser_build_parent],
                                                  help="Build gem from rubygems.org to a specified copr")
    parser_build_rubygems.set_defaults(func="action_build_rubygems")

    # create the parser for the "buildcustom" command
    parser_build_custom = subparsers.add_parser(
            "buildcustom",
            parents=[parser_custom_args_parent, parser_build_parent],
            help="Build packages from SRPM generated by custom script")
    parser_build_custom.set_defaults(func="action_build_custom")

    # create the parser for the "buildfedpkg" command
    parser_build_distgit = subparsers.add_parser("buildfedpkg", parents=[parser_distgit_args_parent, parser_build_parent],
                                                  help="DEPRECATED. Use SCM source type instead.")
    parser_build_distgit.set_defaults(func="action_build_distgit")

    # create the parser for the "buildscm" command
    parser_build_scm = subparsers.add_parser("buildscm", parents=[parser_scm_args_parent, parser_build_parent],
                                              help="Builds package from Git/DistGit/SVN repository.")
    parser_build_scm.set_defaults(func="action_build_scm")

    # create the parser for the "build-distgit" command
    parser_build_distgit_simple = subparsers.add_parser(
        "build-distgit",
        parents=[parser_distgit_simple_parent, parser_build_parent],
        help="Builds a package from a DistGit repository",
        description=(
            "Build a package from a DistGit repository. "
            "For more info about DistGit build method see the description "
            "'add-package-distgit' command."),
    )
    parser_build_distgit_simple.add_argument(
        "--name", dest="pkgname", required=True,
        help=("Package name to build from the DistGit instance"),
    )
    parser_build_distgit_simple.set_defaults(func="action_build_distgit_simple")

    # create the parser for the "status" command
    parser_status = subparsers.add_parser("status", help="Get build status of build specified by its ID")
    parser_status.add_argument("build_id", help="Build ID", type=int)
    parser_status.set_defaults(func="action_status")

    # create the parser for the "download-build" command
    parser_download_build = subparsers.add_parser("download-build", help="Fetches built packages")
    parser_download_build.add_argument("build_id", help="Build ID")
    parser_download_build.add_argument("-r", "--chroot", dest="chroots", action="append",
                                       help="Select chroots to fetch")
    parser_download_build.add_argument("--dest", "-d", dest="dest",
                                       help="Base directory to store packages", default=".")
    parser_download_build.set_defaults(func="action_download_build")

    # create the parser for the "cancel" command
    parser_cancel = subparsers.add_parser("cancel", help="Cancel build specified by its ID")
    parser_cancel.add_argument("build_id", help="Build ID")
    parser_cancel.set_defaults(func="action_cancel")

    # create the parser for the "watch-build" command
    parser_watch = subparsers.add_parser("watch-build",
                                         help="Watch status and progress of build(s)"
                                              " specified by their ID")
    parser_watch.add_argument("build_id", nargs="+",
                              help="Build ID", type=int)
    parser_watch.set_defaults(func="action_watch_build")

    # create the parser for the "delete-build" command
    parser_delete = subparsers.add_parser("delete-build",
                                          help="Delete builds specified by their IDs")
    parser_delete.add_argument("build_id", help="Build ID", type=int, nargs="+")
    parser_delete.set_defaults(func="action_delete_build")

    #########################################################
    ###                   Chroot options                  ###
    #########################################################

    parser_edit_chroot = subparsers.add_parser("edit-chroot", help="Edit chroot of a project")
    parser_edit_chroot.add_argument("coprchroot", help="Path to a project chroot as owner/project/chroot or project/chroot")
    parser_edit_chroot_comps_group = parser_edit_chroot.add_mutually_exclusive_group()
    parser_edit_chroot_comps_group.add_argument("--upload-comps", metavar="FILEPATH",
                                                  help="filepath to the comps.xml file to be uploaded")
    parser_edit_chroot_comps_group.add_argument("--delete-comps", action="store_true",
                                                  help="deletes already existing comps.xml for the chroot")

    parser_edit_chroot.add_argument("--packages",
                                      help="space separated string of package names to be added to buildroot")
    parser_edit_chroot.add_argument("--repos",
                                      help="space separated string of additional repo urls for chroot")
    parser_edit_chroot.add_argument("--isolation", choices=["simple", "nspawn", "default"], default="unchanged",
                                    help="Choose the isolation method for running commands in buildroot.")

    parser_edit_chroot.add_argument(
        "--bootstrap",
        choices=["unchanged", "default", "on", "off", "image"],
        help=("Configure Mock's bootstrap feature, "
              "default is 'unchanged' so the configuration from Copr project "
              "is used for this chroot. "
              "The 'default' variant resets the project configuration "
              "to the pre-configured setup from mock-core-configs. "
              "See 'create --help' for more info."))

    parser_edit_chroot.add_argument(
        "--bootstrap-image",
        help=("Use a custom container image for initializing Mock's "
              "bootstrap (Implies --bootstrap=image)"))

    parser_edit_chroot.set_defaults(func="action_edit_chroot")

    parser_get_chroot = subparsers.add_parser("get-chroot", help="Get chroot of a project")
    parser_get_chroot.add_argument("coprchroot", help="Path to a project chroot as owner/project/chroot or project/chroot")
    parser_get_chroot.set_defaults(func="action_get_chroot")

    parser_list_chroots = subparsers.add_parser("list-chroots", help="List all currently available chroots.")
    parser_list_chroots.set_defaults(func="action_list_chroots")

    #########################################################
    ###                   Package options                 ###
    #########################################################

    # package edit/create parent
    parser_add_or_edit_package_parent = argparse.ArgumentParser(add_help=False)
    parser_add_or_edit_package_parent.add_argument("--name",
                                                   help="Name of the package to be edited or created",
                                                   metavar="PKGNAME", required=True)
    parser_add_or_edit_package_parent.add_argument("copr",
                                                   help="The copr repo for the package. Can be just name of project or even in format username/project or @groupname/project.")
    parser_add_or_edit_package_parent.add_argument("--webhook-rebuild",
                                                   choices=["on", "off"], help="Enable auto-rebuilding.")
    parser_add_or_edit_package_parent.add_argument(
            "--max-builds",
            help="Keep only the specified number of the newest-by-id builds "\
                 "(garbage collector is run daily), zero disables (default)")

    # PyPI edit/create
    parser_add_package_pypi = subparsers.add_parser("add-package-pypi",
                                                    help="Creates a new PyPI package",
                                                    parents=[parser_pypi_args_parent, parser_add_or_edit_package_parent])
    parser_add_package_pypi.set_defaults(func="action_add_or_edit_package_pypi", create=True)

    parser_edit_package_pypi = subparsers.add_parser("edit-package-pypi",
                                                     help="Edits an existing PyPI package",
                                                     parents=[parser_pypi_args_optional, parser_add_or_edit_package_parent])
    parser_edit_package_pypi.add_argument("--packagename", required=False, metavar="PYPINAME",
                                          help="Name of the PyPI package to be built, required.")
    parser_edit_package_pypi.set_defaults(func="action_add_or_edit_package_pypi", create=False)


    # SCM edit/create
    parser_add_package_scm = subparsers.add_parser("add-package-scm",
                                                       help="Creates a new SCM package.",
                                                       parents=[parser_scm_args_parent, parser_add_or_edit_package_parent])
    parser_add_package_scm.set_defaults(func="action_add_or_edit_package_scm", create=True)

    parser_edit_package_scm = subparsers.add_parser("edit-package-scm",
                                                        help="Edits an existing SCM package.",
                                                        parents=[parser_scm_args_parent, parser_add_or_edit_package_parent])
    parser_edit_package_scm.set_defaults(func="action_add_or_edit_package_scm", create=False)

    # DistGit edit/create package
    parser_add_package_distgit = subparsers.add_parser(
        "add-package-distgit",
        help="Creates a new DistGit package",
        description=(
            "DistGit (Distribution Git) is Git with additional data "
            "storage (so called \"lookaside cache\"). It is designed to hold "
            "content of source RPMs. For more info, see the "
            "https://github.com/release-engineering/dist-git documentation."
            "\n\n"
            "To build a package for a particular distribution, you need "
            "clone the correct git repository, and download corresponding "
            "sources files from the lookaside cache.  Each distribution though "
            "uses a different hostname for DistGit server and may store the "
            "git repositories and source files on a little bit different "
            "URIs (or even in NAMESPACEs).  That's why Copr has this "
            "build method pre-configured as \"DistGit instances\" (one "
            "instance per one distribution)."
        ),
        parents=[parser_distgit_simple_parent,
                 parser_add_or_edit_package_parent])
    parser_add_package_distgit.set_defaults(
        func="action_add_or_edit_package_distgit",
        create=True)
    parser_edit_package_distgit = subparsers.add_parser(
        "edit-package-distgit",
        help="Edits an existing DistGit package",
        description=(
            "Edit an existing DistGit package.  For more info about DistGit "
            "build method see the description of 'add-package-distgit' "
            "command."),
        parents=[parser_distgit_simple_parent,
                 parser_add_or_edit_package_parent])
    parser_edit_package_distgit.set_defaults(
        func="action_add_or_edit_package_distgit",
        create=False)

    # Rubygems edit/create
    parser_add_package_rubygems = subparsers.add_parser("add-package-rubygems",
                                                        help="Creates a new RubyGems package",
                                                        parents=[parser_rubygems_args_parent, parser_add_or_edit_package_parent])
    parser_add_package_rubygems.set_defaults(func="action_add_or_edit_package_rubygems", create=True)

    parser_edit_package_rubygems = subparsers.add_parser("edit-package-rubygems",
                                                         help="Edits an existing RubyGems package",
                                                         parents=[parser_rubygems_args_parent, parser_add_or_edit_package_parent])
    parser_edit_package_rubygems.set_defaults(func="action_add_or_edit_package_rubygems", create=False)

    # Custom build method - edit/create package
    parser_add_package_custom = subparsers.add_parser(
            "add-package-custom",
            help="Creates a new package where sources are built by custom script",
            parents=[parser_custom_args_parent, parser_add_or_edit_package_parent])
    parser_add_package_custom.set_defaults(
            func="action_add_or_edit_package_custom",
            create=True)
    parser_edit_package_custom = subparsers.add_parser(
            "edit-package-custom",
            help="Edits an existing Custom package",
            parents=[parser_custom_args_parent, parser_add_or_edit_package_parent])
    parser_edit_package_custom.set_defaults(
            func="action_add_or_edit_package_custom",
            create=False)

    # package listing
    parser_list_packages = subparsers.add_parser("list-packages",
                                                 help="Returns list of packages in the given copr")
    parser_list_packages.add_argument("copr",
                                      help="The copr repo to list the packages of. Can be just name of project or even in format owner/project.")
    parser_list_packages.add_argument("--with-latest-build", action="store_true",
                                      help="Also display data related to the latest build for the package.")
    parser_list_packages.add_argument("--with-latest-succeeded-build", action="store_true",
                                      help="Also display data related to the latest succeeded build for the package.")
    parser_list_packages.add_argument("--with-all-builds", action="store_true",
                                      help="Also display data related to the builds for the package.")
    parser_list_packages.set_defaults(func="action_list_packages")

    # package names listing
    parser_list_package_names = subparsers.add_parser("list-package-names",
                                                      help="Returns list of package names in the given copr")
    parser_list_package_names.add_argument("copr",
                                           help="The copr repo to list the packages of. Can be just name of project or even in format owner/project.")
    parser_list_package_names.set_defaults(func="action_list_package_names")

    # single package fetching
    parser_get_package = subparsers.add_parser("get-package",
                                               help="Returns package of the given name in the given copr")
    parser_get_package.add_argument("copr",
                                    help="The copr repo to list the packages of. Can be just name of project or even in format owner/project.")
    parser_get_package.add_argument("--name",
                                    help="Name of a single package to be displayed",
                                    metavar="PKGNAME", required=True)
    parser_get_package.add_argument("--with-latest-build", action="store_true",
                                    help="Also display data related to the latest build for each package.")
    parser_get_package.add_argument("--with-latest-succeeded-build", action="store_true",
                                    help="Also display data related to the latest succeeded build for each package.")
    parser_get_package.add_argument("--with-all-builds", action="store_true",
                                    help="Also display data related to the builds for each package.")
    parser_get_package.set_defaults(func="action_get_package")

    # package deletion
    parser_delete_package = subparsers.add_parser("delete-package",
                                                  help="Deletes the specified package")
    parser_delete_package.add_argument("copr",
                                       help="The copr repo to list the packages of. Can be just name of project or even in format owner/project.")
    parser_delete_package.add_argument("--name",
                                       help="Name of a package to be deleted",
                                       metavar="PKGNAME", required=True)
    parser_delete_package.set_defaults(func="action_delete_package")

    # package reseting
    parser_reset_package = subparsers.add_parser("reset-package",
                                                 help="Resets (clears) default source of the specified package")
    parser_reset_package.add_argument("copr",
                                      help="The copr repo to list the packages of. Can be just name of project or even in format owner/project.")
    parser_reset_package.add_argument("--name",
                                      help="Name of a package to be reseted",
                                      metavar="PKGNAME", required=True)
    parser_reset_package.set_defaults(func="action_reset_package")

    # package building
    parser_build_package = subparsers.add_parser("build-package", parents=[parser_build_parent],
                                                 help="Builds the package from its default source")
    parser_build_package.add_argument("--name",
                                      help="Name of a package to be built",
                                      metavar="PKGNAME", required=True)
    parser_build_package.set_defaults(func="action_build_package")

    # module building
    parser_build_module = subparsers.add_parser("build-module", help="Builds a given module in Copr")
    parser_build_module.add_argument("copr", help="The copr repo to build module in. Can be just name of project or even in format owner/project.")
    parser_build_module_mmd_source = parser_build_module.add_mutually_exclusive_group(required=True)
    parser_build_module_mmd_source.add_argument("--url", help="SCM with modulemd file in yaml format")
    parser_build_module_mmd_source.add_argument("--yaml", help="Path to modulemd file in yaml format")
    parser_build_module.set_defaults(func="action_build_module")
    parser_build_module.add_argument(
        "--distgit",
        help="Dist-git instance to build against, e.g. 'fedora'"
    )


    #########################################################
    ###                   Permissions actions             ###
    #########################################################

    def make_permission_action(role, default_permission, default_username=None):
        class CustomAction(argparse.Action):
            def __call__(self, parser, args, argument, option_string=None):
                permission = self.default_permission
                username = self.default_username
                if not username:
                    # User required, user=permission allowed.
                    if '=' in argument:
                        splitted = argument.split('=')
                        permission = splitted.pop()
                        username = '='.join(splitted)
                    else:
                        username = argument
                else:
                    # username predefined (myself)
                    if argument:
                        permission = argument
                if not args.permissions:
                    args.permissions = {}
                if not username in args.permissions:
                    args.permissions[username] = {}
                if role in args.permissions[username]:
                    raise argparse.ArgumentError(
                        self, "requested more than once for {0}".format(username))
                args.permissions[username][role] = permission

        CustomAction.default_permission = default_permission
        CustomAction.default_username = default_username
        return CustomAction

    parser_permissions_edit = subparsers.add_parser(
            "edit-permissions",
            help="Edit roles/permissions on a copr project")
    parser_permissions_edit.add_argument("project",
            metavar='PROJECT',
            help="An existing copr project")
    edit_help = """Set the '{0}' role for USERNAME in PROJECT, VALUE can be one
            of 'approved|request|nothing' (default=approved)"""
    parser_permissions_edit.add_argument("--admin",
            metavar='USERNAME[=VALUE]',
            dest='permissions',
            action=make_permission_action('admin', 'approved'),
            help=edit_help.format('admin'))
    parser_permissions_edit.add_argument("--builder",
            metavar='USERNAME[=VALUE]',
            dest='permissions',
            action=make_permission_action('builder', 'approved'),
            help=edit_help.format('builder'))
    parser_permissions_edit.set_defaults(func='action_permissions_edit')

    # list
    parser_permissions_list = subparsers.add_parser(
            "list-permissions",
            help="Print the copr project roles/permissions")
    parser_permissions_list.add_argument("project",
            metavar='PROJECT',
            help="An existing copr project")
    parser_permissions_list.set_defaults(func='action_permissions_list')

    # request
    parser_permissions_request = subparsers.add_parser(
            "request-permissions",
            help="Request (or reject) your role in the copr project")
    parser_permissions_request.add_argument("project",
            metavar='PROJECT',
            help="An existing copr project")
    request_help = """Request/cancel request/remove your '{0}' permissions in
            PROJECT.  VALUE can be one of 'request|nothing', default=request
            """
    parser_permissions_request.add_argument(
            "--admin", nargs='?',
            action=make_permission_action('admin', 'request', 'your user'),
            dest='permissions',
            help=request_help.format('admin'))
    parser_permissions_request.add_argument(
            "--builder", nargs='?',
            action=make_permission_action('builder', 'request', 'your user'),
            dest='permissions',
            help=request_help.format('builder'))
    parser_permissions_request.set_defaults(func='action_permissions_request')

    if argcomplete:
        argcomplete.autocomplete(parser)
    return parser


def enable_debug():
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    sys.stderr.write("#  Debug log enabled  #\n")


def str2bool(v):
    if v.lower() in ("yes", "true", "on", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "off", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def main(argv=sys.argv[1:]):
    try:
        # Set up parser for global args
        parser = setup_parser()
        # Parse the commandline
        arg = parser.parse_args(argv)
        if arg.debug:
            enable_debug()

        if not "func" in arg:
            parser.print_help()
            return

        commands = Commands(arg.config)
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
    except (CoprRequestException, CoprNoResultException) as e:
        sys.stderr.write("\nSomething went wrong:")
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(1)
    except argparse.ArgumentTypeError as e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(2)
    except CoprException as e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(3)
    except FrontendOutdatedCliException as e:
        sys.stderr.write("\nError: {0}\n".format(e))
        sys.exit(5)

        # except Exception as e:
        # print "Error: {0}".format(e)
        # sys.exit(100)


if __name__ == "__main__":
    main()
