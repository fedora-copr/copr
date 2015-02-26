#!/usr/bin/python -tt
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


# Original approach was:
# take list of pkgs
# take single hostname
# send 1 pkg at a time to host
# build in remote w/mockchain
# rsync results back
# repeat
# take args from mockchain (more or less)

# now we build only one package per MockRemote instance

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import fcntl
import os

from bunch import Bunch
import time

from ..constants import DEF_REMOTE_BASEDIR, DEF_BUILD_TIMEOUT, DEF_REPOS, \
    DEF_BUILD_USER, DEF_MACROS
from ..exceptions import MockRemoteError, BuilderError


# TODO: replace sign & createrepo with dependency injection
from ..sign import sign_rpms_in_dir, get_pubkey
from ..createrepo import createrepo

from .builder import Builder
from .callback import DefaultCallBack


def get_target_dir(chroot_dir, pkg_name):
    source_basename = os.path.basename(pkg_name).replace(".src.rpm", "")
    return os.path.normpath(os.path.join(chroot_dir, source_basename))


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

    def __init__(self, builder_host=None, job=None,
                 repos=None,
                 callback=None,
                 opts=None,
                 lock=None):

        """
        :param builder_host: builder hostname or ip

        :param backend.job.BuildJob job: Job object with the following attributes::
            :ivar timeout: ssh timeout
            :ivar destdir: target directory to put built packages
            :ivar chroot: chroot config name/base to use in the mock build
                           (e.g.: fedora20_i386 )
            :ivar buildroot_pkgs: whitespace separated string with additional
                               packages that should present during build
            :ivar build_id: copr build.id
            :ivar pkg: pkg to build


        :param repos: additional repositories for mock
        :param backend.mockremote.callback.DefaultCallBack callback: object with hooks for notifications
                                         about build progress

        :param macros: {    "copr_username": ...,
                            "copr_projectname": ...,
                            "vendor": ...}
        :param multiprocessing.Lock lock: instance of Lock shared between
            Copr backend process
        :param DefaultCallback callback: build progress handler

        :param Bunch opts: builder options, used keys::
            :ivar build_user: user to run as/connect as on builder systems
            :ivar do_sign: enable package signing, require configured
                signer host and correct /etc/sign.conf
            :ivar frontend_base_url: url to the copr frontend
            :ivar results_baseurl: base url for the built results
            :ivar remote_basedir: basedir on builder
            :ivar remote_tempdir: tempdir on builder

        # Removed:
        # :param cont: if a pkg fails to build, continue to the next one--
        # :param bool recurse: if more than one pkg and it fails to build,
        #                      try to build the rest and come back to it
        """
        self.opts = Bunch(
            do_sign=False,
            frontend_base_url=None,
            results_baseurl=u"",
            build_user=DEF_BUILD_USER,
            remote_basedir=DEF_REMOTE_BASEDIR,
            remote_tempdir=None,
        )
        if opts:
            self.opts.update(opts)

        self.job = job
        self.repos = repos or DEF_REPOS

        # TODO: remove or re-implement
        # self.cont = cont    # unused since we build only one pkg at time
        # self.recurse = recurse

        self.callback = callback
        self.lock = lock

        if not self.callback:
            self.callback = DefaultCallBack()

        self.callback.log("Setting up builder: {0}".format(builder_host))
        self.builder = Builder(
            opts=self.opts,
            hostname=builder_host,
            job=self.job,
            callback=self.callback,
            repos=self.repos
        )

        self.failed = []
        self.finished = []


        # self.callback.log("MockRemote: {}".format(self.__dict__))

    def check(self):
        """
        Checks that MockRemote configuration and environment are correct.

        :raises MockRemoteError: when configuration is wrong or
            some expected resource is unavailable
        """
        if not self.job.chroot:
            raise MockRemoteError("No chroot specified!")

        self.builder.check()

    @property
    def chroot_dir(self):
        return os.path.normpath(os.path.join(self.job.destdir, self.job.chroot))

    @property
    def pkg(self):
        return self.job.pkg

    def _get_pkg_destpath(self, pkg):
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace(".src.rpm", "")
        return os.path.normpath(
            "{0}/{1}/{2}".format(self.job.destdir, self.job.chroot, pdn))

    def add_pubkey(self):
        """
            Adds pubkey.gpg with public key to ``chroot_dir``
            using `copr_username` and `copr_projectname` from self.job.
        """
        self.callback.log("Retrieving pubkey ")
        # TODO: sign repodata as well ?
        user = self.job.project_owner
        project = self.job.project_name
        pubkey_path = os.path.join(self.job.destdir, "pubkey.gpg")
        try:
            # TODO: uncomment this when key revoke/change will be implemented
            # if os.path.exists(pubkey_path):
            #    return

            get_pubkey(user, project, pubkey_path)
            self.callback.log(
                "Added pubkey for user {} project {} into: {}".
                format(user, project, pubkey_path))

        except Exception as e:
            self.callback.error(
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

        self.callback.log("Going to sign pkgs from source: {} in chroot: {}".
                          format(self.pkg, self.chroot_dir))

        try:
            sign_rpms_in_dir(self.job.project_owner,
                             self.job.project_name,
                             get_target_dir(self.chroot_dir, self.pkg),
                             opts=self.opts,
                             callback=self.callback,)
        except Exception as e:
            self.callback.error(
                "failed to sign packages "
                "built from `{}` with error: \n"
                "{}".format(self.pkg, e)
            )
            if isinstance(e, MockRemoteError):
                raise e

        self.callback.log("Sign done")

    @staticmethod
    def log_to_file_safe(filepath, to_out_list, to_err_list):
        r_log = open(filepath, 'a')
        fcntl.flock(r_log, fcntl.LOCK_EX)
        for to_out in to_out_list:
            r_log.write(to_out)
        if to_err_list:
            r_log.write("\nstderr\n")
            for to_err in to_err_list:
                r_log.write(str(to_err))
        fcntl.flock(r_log, fcntl.LOCK_UN)
        r_log.close()

    def do_createrepo(self):
        base_url = "/".join([self.opts.results_baseurl, self.job.project_owner,
                             self.job.project_name, self.job.chroot])
        self.callback.log("Createrepo:: owner:  {}; project: {}; "
                          "front url: {}; path: {}; base_url: {}"
                          .format(self.job.project_owner, self.job.project_name,
                                  self.opts.frontend_base_url, self.chroot_dir, base_url))

        _, _, err = createrepo(
            path=self.chroot_dir,
            front_url=self.opts.frontend_base_url,
            base_url=base_url,
            username=self.job.project_owner,
            projectname=self.job.project_name,
            lock=self.lock,
        )
        if err.strip():
            self.callback.error(
                "Error making local repo: {0}".format(self.chroot_dir))

            self.callback.error(str(err))
            # FIXME - maybe clean up .repodata and .olddata
            # here?

    def on_success_build(self):
        self.callback.log("Success building {0}".format(os.path.basename(self.pkg)))

        if self.opts.do_sign:
            self.sign_built_packages()

        # createrepo with the new pkgs
        self.do_createrepo()

    def prepare_build_dir(self):
        # TODO: remove old logs (build.log*, root.log*)
        p_path = self._get_pkg_destpath(self.pkg)
        # if it's marked as fail, nuke the failure and try to rebuild it
        if os.path.exists(os.path.join(p_path, "fail")):
            os.unlink(os.path.join(p_path, "fail"))

        if os.path.exists(os.path.join(p_path, "success")):
            os.unlink(os.path.join(p_path, "success"))

        # mkdir to download results
        if not os.path.exists(p_path):
            os.makedirs(p_path)

        self.mark_dir_with_build_id()

    def build_pkg_and_process_results(self):
        self.prepare_build_dir()

        # building
        self.callback.start_build(self.pkg)

        build_stdout = ""
        build_error = build_details = None
        try:
            build_details, build_stdout = self.builder.build(self.pkg)
            self.callback.log("builder.build finished; details: {}\n stdout: {}".format(build_details, build_stdout))
        except BuilderError as error:
            self.callback.log("builder.build error building pkg `{}`: {}".format(self.pkg, error))
            build_error = error

        # TODO: try to use
        # finally:

        self.callback.end_build(self.pkg)

        # downloading
        self.callback.start_download(self.pkg)
        self.builder.download(self.pkg, self.chroot_dir)
        self.callback.end_download(self.pkg)

        # add record to mockchain.log # TODO:
        if build_error is not None:
            stderr_to_log = build_error.stderr
        else:
            stderr_to_log = ""
        self.log_to_file_safe(os.path.join(self.chroot_dir, "mockchain.log"),
                              ["\n\n{0}\n\n".format(self.pkg), build_stdout], [stderr_to_log])

        if build_error:
            raise MockRemoteError("Error occurred during build {}: {}"
                                  .format(os.path.basename(self.pkg), build_error))

        self.on_success_build()
        return build_details

    def mark_dir_with_build_id(self):
        """
            Places "build.info" which contains job build_id
                into the directory with downloaded files.

        """
        info_file_path = os.path.join(self._get_pkg_destpath(self.job.pkg),
                                      "build.info")
        self.callback.log("mark build dir with build_id, ")
        try:
            with open(info_file_path, 'w') as info_file:
                info_file.writelines(["build_id={}".format(self.job.build_id),])

        except Exception as error:
            msg = "Failed to mark build {} with build_id".format(error)
            self.callback.log(msg)
