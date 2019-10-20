# by skvidal
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
# copyright 2012 Red Hat, Inc.

import fcntl
import logging
import os
import subprocess

from munch import Munch
import time

from ..constants import DEF_BUILD_TIMEOUT, DEF_REPOS, \
    DEF_BUILD_USER, DEF_MACROS
from ..exceptions import MockRemoteError, BuilderError, CreateRepoError
from ..helpers import uses_devel_repo


# TODO: replace sign & createrepo with dependency injection
from ..sign import sign_rpms_in_dir, get_pubkey
from ..createrepo import createrepo

from .builder import Builder, SrpmBuilder


# class BuilderThread(object):
#     def __init__(self, builder_obj):
#         self.builder = builder_obj
#         self._running = False
#
#     def terminate(self):
#         self._running = False
#
#     def run(self):
#         self.builder.start_build()
#         self._running = True
#         state = None
#         while self._running:
#             state = self.builder.update_progress()
#             if state in ["done", "failed"]:
#                 self._running = False
#             else:
#                 time.sleep(5)
#
#         if state == "done":
#             self.builder.after_build()


class MockRemote(object):
    # TODO: Refactor me!
    #   mock remote now do too much things
    #   idea: send events according to the build progress to handler

    def __init__(self, builder_host, job, logger,
                 opts=None):

        """
        :param builder_host: builder hostname or ip

        :param backend.job.BuildJob job: Job object with the following attributes::
            :ivar timeout: ssh timeout
            :ivar destdir: target directory to put built packages
            :ivar chroot: chroot config name/base to use in the mock build
                           (e.g.: fedora20_i386 )
            :ivar build_id: copr build.id
            :ivar pkg: pkg to build


        :param macros: {    "copr_username": ...,
                            "copr_projectname": ...,
                            "vendor": ...}

        :param Munch opts: builder options, used keys::
            :ivar build_user: user to run as/connect as on builder systems
            :ivar do_sign: enable package signing, require configured
                signer host and correct /etc/sign.conf
            :ivar frontend_base_url: url to the copr frontend
            :ivar results_baseurl: base url for the built results

        # Removed:
        # :param cont: if a pkg fails to build, continue to the next one--
        # :param bool recurse: if more than one pkg and it fails to build,
        #                      try to build the rest and come back to it
        """
        self.opts = Munch(
            do_sign=False,
            frontend_base_url=None,
            results_baseurl=u"",
            build_user=DEF_BUILD_USER,
            timeout=DEF_BUILD_TIMEOUT,
        )
        if opts:
            self.opts.update(opts)

        self.log = logger
        self.job = job

        self.log.info("Setting up builder: {0}".format(builder_host))
        # TODO: add option "builder_log_level" to backend config
        self.log.setLevel(logging.INFO)

        builder_cls = (SrpmBuilder if self.job.chroot == 'srpm-builds' else Builder)

        self.builder = builder_cls(
            opts=self.opts,
            hostname=builder_host,
            job=self.job,
            logger=logger,
        )

        self.failed = []
        self.finished = []

    def check(self):
        """
        Checks that MockRemote configuration and environment are correct.

        :raises MockRemoteError: when configuration is wrong or
            some expected resource is unavailable
        """
        if not self.job.chroot:
            raise MockRemoteError("No chroot specified!")

        try:
            self.builder.check()
        except BuilderError as error:
            raise MockRemoteError(str(error))

    @property
    def chroot_dir(self):
        return os.path.normpath(os.path.join(self.job.destdir, self.job.chroot))

    @property
    def pkg(self):
        return self.job.pkg

    def add_pubkey(self):
        """
            Adds pubkey.gpg with public key to ``chroot_dir``
            using `copr_username` and `copr_projectname` from self.job.
        """
        self.log.info("Retrieving pubkey ")
        # TODO: sign repodata as well ?
        user = self.job.project_owner
        project = self.job.project_name
        pubkey_path = os.path.join(self.job.destdir, "pubkey.gpg")
        try:
            # TODO: uncomment this when key revoke/change will be implemented
            # if os.path.exists(pubkey_path):
            #    return

            get_pubkey(user, project, pubkey_path)
            self.log.info(
                "Added pubkey for user {} project {} into: {}".
                format(user, project, pubkey_path))

        except Exception as e:
            self.log.exception(
                "failed to retrieve pubkey for user {} project {} due to: \n"
                "{}".format(user, project, e))

    def sign_built_packages(self):
        """
            Sign built rpms
             using `copr_username` and `copr_projectname` from self.job
             by means of obs-sign. If user builds doesn't have a key pair
             at sign service, it would be created through ``copr-keygen``

        :param chroot_dir: Directory with rpms to be signed
        :param pkg: path to the source package

        """

        self.log.info("Going to sign pkgs from source: {} in chroot: {}"
                      .format(self.job, self.chroot_dir))

        try:
            sign_rpms_in_dir(
                self.job.project_owner,
                self.job.project_name,
                os.path.join(self.chroot_dir, self.job.target_dir_name),
                opts=self.opts,
                log=self.log
            )
        except Exception as e:
            self.log.exception(
                "failed to sign packages built from `{}` with error".format(self.job))
            if isinstance(e, MockRemoteError):
                raise

        self.log.info("Sign done")

    def do_createrepo(self):
        if self.job.chroot == 'srpm-builds':
            return

        project_owner = self.job.project_owner
        project_name = self.job.project_name
        devel = self.job.uses_devel_repo

        base_url = "/".join([self.opts.results_baseurl, project_owner,
                             project_name, self.job.chroot])
        self.log.info("Createrepo:: owner:  {}; project: {}; "
                      "front url: {}; path: {}; base_url: {}"
                      .format(project_owner, project_name,
                              self.opts.frontend_base_url, self.chroot_dir, base_url))
        try:
            createrepo(
                path=self.chroot_dir,
                base_url=base_url,
                username=project_owner,
                projectname=project_name,
                devel=devel,
            )
        except CreateRepoError:
            self.log.exception("Error making local repo: {}".format(self.chroot_dir))

            # FIXME - maybe clean up .repodata and .olddata
            # here?

    def on_success_build(self):
        self.log.info("Success building {0}".format(self.job.package_name))

        if self.opts.do_sign:
            self.sign_built_packages()

        # createrepo with the new pkgs
        self.do_createrepo()

    def prepare_build_dir(self):
        p_path = self.job.results_dir
        # if it's marked as fail, nuke the failure and try to rebuild it
        if os.path.exists(os.path.join(p_path, "fail")):
            os.unlink(os.path.join(p_path, "fail"))

        if os.path.exists(os.path.join(p_path, "success")):
            os.unlink(os.path.join(p_path, "success"))

        # mkdir to download results
        if not os.path.exists(p_path):
            os.makedirs(p_path)

        self.mark_dir_with_build_id()

    # def add_log_symlinks(self):
    #     # adding symlinks foo.log.gz -> foo.log for nginx web server auto index
    #     try:
    #         base = self._get_pkg_destpath()
    #         for name in os.listdir(base):
    #             if not name.endswith(".log.gz"):
    #                 continue
    #             full_path = os.path.join(base, name)
    #             if os.path.isfile(full_path):
    #                 os.symlink(full_path, full_path.replace(".log.gz", ".log"))
    #     except Exception as err:
    #         self.log.exception(err)

    def build_pkg(self):
        self.log.info("Start build: {}".format(self.job))

        self.prepare_build_dir()

        try:
            self.builder.build()
        except BuilderError as error:
            self.log.error(str(error))
            raise MockRemoteError("Builder error during job {}.".format(self.job))

    def compress_live_log(self, job):
        log_basename = "builder-live.log"
        src = os.path.join(job.results_dir, log_basename)

        # For automatic redirect from log to log.gz, consider configuring
        # lighttpd like:
        #     url.rewrite-if-not-file = ("^/(.*)/builder-live.log$" => "/$1/redirect-live.log")
        #     url.redirect("^/(.*)/redirect-live.log$" => "/$1/builder-live.log.gz")
        # or apache by:
        #     <Files builder-live.log>
        #     RewriteEngine on
        #     RewriteCond %{REQUEST_FILENAME} !-f
        #     RewriteRule ^(.*)$ %{REQUEST_URI}.gz [R]
        #     </files>
        self.log.info("Compressing {} by gzip".format(src))
        if subprocess.call(["gzip", src]) not in [0, 2]:
            self.log.error("Unable to compress file {}".format(src))
            return

    def reattach_to_pkg_build(self):
        """
        :raises VmError, BuilderError
        """
        self.log.info("Reattach to build: {}".format(self.job))

        try:
            self.builder.reattach()
        except BuilderError as error:
            self.log.error(str(error))
            raise MockRemoteError("Builder error during job {}.".format(self.job))

    def check_build_success(self):
        """
        Raise MockRemoteError if builder claims that the build failed.
        """
        if not self.builder.check_build_success():
            raise MockRemoteError("Build {} failed".format(self.job))

    def download_results(self):
        try:
            self.builder.download_results(self.job.results_dir)
        except Exception as err:
            self.log.exception(err)

    def mark_dir_with_build_id(self):
        """
            Places "build.info" which contains job build_id
                into the directory with downloaded files.

        """
        info_file_path = os.path.join(self.job.results_dir, "build.info")
        self.log.info("marking build dir with build_id, ")
        try:
            with open(info_file_path, 'w') as info_file:
                info_file.writelines([
                    "build_id={}".format(self.job.build_id),
                    "\nbuilder_ip={}".format(self.builder.hostname)])

        except Exception as error:
            self.log.exception("Failed to mark build {} with build_id".format(error))
