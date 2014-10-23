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


# take list of pkgs
# take single hostname
# send 1 pkg at a time to host
# build in remote w/mockchain
# rsync results back
# repeat
# take args from mockchain (more or less)

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import sys
import time
import fcntl
import pipes
import socket
import urllib
import subprocess
import os

import ansible.runner

from .helpers import SortedOptParser
from .exceptions import MockRemoteError, BuilderError
from .sign import sign_rpms_in_dir, get_pubkey


# where we should execute mockchain from on the remote
mockchain = "/usr/bin/mockchain"
# rsync path
rsync = "/usr/bin/rsync"

DEF_REMOTE_BASEDIR = "/var/tmp"
DEF_TIMEOUT = 3600
DEF_REPOS = []
DEF_CHROOT = None
DEF_USER = "mockbuilder"
DEF_DESTDIR = os.getcwd()
DEF_MACROS = {}
DEF_BUILDROOT_PKGS = ""

from .createrepo import createrepo

def createrepo_orig(path, lock=None):
    comm = ['/usr/bin/createrepo_c', '--database', '--ignore-lock']
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm.append("--update")
    if "epel-5" in path:
        # this is because rhel-5 doesn't know sha256
        comm.extend(['-s', 'sha', '--checksum', 'md5'])
    comm.append(path)

    if lock:
        lock.acquire()
    cmd = subprocess.Popen(comm,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = cmd.communicate()
    if lock:
        lock.release()
    return cmd.returncode, out, err


def read_list_from_file(fn):
    lst = []
    f = open(fn, "r")
    for line in f.readlines():
        line = line.replace("\n", "")
        line = line.strip()
        if line.startswith("#"):
            continue
        lst.append(line)

    return lst


def log(lf, msg, quiet=None):
    if lf:
        now = time.time()
        try:
            with open(lf, "a") as lfh:
                fcntl.flock(lfh, fcntl.LOCK_EX)
                lfh.write(str(now) + ":" + msg + "\n")
                fcntl.flock(lfh, fcntl.LOCK_UN)
        except (IOError, OSError) as e:
            sys.stderr.write(
                "Could not write to logfile {0} - {1}\n".format(lf, str(e)))
    if not quiet:
        print(msg)


def get_ans_results(results, hostname):
    if hostname in results["dark"]:
        return results["dark"][hostname]
    if hostname in results["contacted"]:
        return results["contacted"][hostname]

    return {}


def _create_ans_conn(hostname, username, timeout):
    ans_conn = ansible.runner.Runner(remote_user=username,
                                     host_list=hostname + ",",
                                     pattern=hostname,
                                     forks=1,
                                     transport="ssh",
                                     timeout=timeout)
    return ans_conn


def check_for_ans_error(results, hostname, err_codes=None, success_codes=None,
                        return_on_error=None):
    """
    Return True or False + dict
    dict includes 'msg'
    may include 'rc', 'stderr', 'stdout' and any other requested result codes
    """

    if err_codes is None:
        err_codes = []
    if success_codes is None:
        success_codes = [0]
    if return_on_error is None:
        return_on_error = ["stdout", "stderr"]
    err_results = {}

    if "dark" in results and hostname in results["dark"]:
        err_results["msg"] = "Error: Could not contact/connect" \
            " to {0}.".format(hostname)

        return True, err_results

    error = False

    if err_codes or success_codes:
        if hostname in results["contacted"]:
            if "rc" in results["contacted"][hostname]:
                rc = int(results["contacted"][hostname]["rc"])
                err_results["rc"] = rc
                # check for err codes first
                if rc in err_codes:
                    error = True
                    err_results["msg"] = "rc {0} matched err_codes".format(rc)
                elif rc not in success_codes:
                    error = True
                    err_results["msg"] = "rc {0} not in success_codes".format(rc)

            elif ("failed" in results["contacted"][hostname] and
                    results["contacted"][hostname]["failed"]):

                error = True
                err_results["msg"] = "results included failed as true"

        if error:
            for item in return_on_error:
                if item in results["contacted"][hostname]:
                    err_results[item] = results["contacted"][hostname][item]

    return error, err_results


class DefaultCallBack(object):

    def __init__(self, **kwargs):
        self.quiet = kwargs.get("quiet", False)
        self.logfn = kwargs.get("logfn", None)

    def start_build(self, pkg):
        pass

    def end_build(self, pkg):
        pass

    def start_download(self, pkg):
        pass

    def end_download(self, pkg):
        pass

    def error(self, msg):
        self.log("Error: {0}".format(msg))

    def log(self, msg):
        if not self.quiet:
            print(msg)


class CliLogCallBack(DefaultCallBack):

    def __init__(self, **kwargs):
        DefaultCallBack.__init__(self, **kwargs)

    def start_build(self, pkg):
        msg = "Start build: {0}".format(pkg)
        self.log(msg)

    def end_build(self, pkg):
        msg = "End Build: {0}".format(pkg)
        self.log(msg)

    def start_download(self, pkg):
        msg = "Start retrieve results for: {0}".format(pkg)
        self.log(msg)

    def end_download(self, pkg):
        msg = "End retrieve results for: {0}".format(pkg)
        self.log(msg)

    def error(self, msg):
        self.log("Error: {0}".format(msg))

    def log(self, msg):
        log(self.logfn, msg, self.quiet)


class Builder(object):

    def __init__(self, hostname, username,
                 timeout, mockremote, buildroot_pkgs):

        self.hostname = hostname
        self.username = username
        self.timeout = timeout
        self.chroot = mockremote.chroot
        self.repos = mockremote.repos
        self.mockremote = mockremote

        if buildroot_pkgs is None:
            self.buildroot_pkgs = ""
        else:
            self.buildroot_pkgs = buildroot_pkgs

        self.checked = False
        self._tempdir = None
        # if we're at this point we've connected and done stuff on the host
        self.conn = _create_ans_conn(
            self.hostname, self.username, self.timeout)
        self.root_conn = _create_ans_conn(self.hostname, "root", self.timeout)
        # check out the host - make sure it can build/be contacted/etc
        self.check()

    @property
    def remote_build_dir(self):
        return self.tempdir + "/build/"

    @property
    def tempdir(self):
        if self.mockremote.remote_tempdir:
            return self.mockremote.remote_tempdir

        if self._tempdir:
            return self._tempdir

        cmd = "/bin/mktemp -d {0}/{1}-XXXXX".format(
            self.mockremote.remote_basedir, "mockremote")

        self.conn.module_name = "shell"
        self.conn.module_args = str(cmd)
        results = self.conn.run()
        tempdir = None
        for _, resdict in results["contacted"].items():
            tempdir = resdict["stdout"]

        # if still nothing then we"ve broken
        if not tempdir:
            raise BuilderError("Could not make tmpdir on {0}".format(
                self.hostname))

        cmd = "/bin/chmod 755 {0}".format(tempdir)
        self.conn.module_args = str(cmd)
        self.conn.run()
        self._tempdir = tempdir

        return self._tempdir

    @tempdir.setter
    def tempdir(self, value):
        self._tempdir = value

    def _get_remote_pkg_dir(self, pkg):
        # the pkg will build into a dir by mockchain named:
        # $tempdir/build/results/$chroot/$packagename
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace(".src.rpm", "")
        remote_pkg_dir = os.path.normpath(
            os.path.join(self.remote_build_dir,
                         "results",
                         self.chroot,
                         pdn))

        return remote_pkg_dir

    def modify_base_buildroot(self):
        """
        Modify mock config for current chroot.

        Packages in buildroot_pkgs are added to minimal buildroot
        """

        if ("'{0} '".format(self.buildroot_pkgs) !=
                pipes.quote(str(self.buildroot_pkgs) + ' ')):

            # just different test if it contains only alphanumeric characters
            # allowed in packages name
            raise BuilderError("Do not try this kind of attack on me")

        self.root_conn.module_name = "lineinfile"
        self.root_conn.module_args = (
            "dest=/etc/mock/{0}.cfg"
            " line=\"config_opts['chroot_setup_cmd'] ="
            " 'install @buildsys-build {1}'\""
            " regexp=\"^.*chroot_setup_cmd.*$\"".format(
                self.chroot, self.buildroot_pkgs))

        self.mockremote.callback.log(
            "putting {0} into minimal buildroot of {1}".format(
                self.buildroot_pkgs, self.chroot))

        results = self.root_conn.run()

        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0],
            return_on_error=["stdout", "stderr"])

        if is_err:
            self.mockremote.callback.log("Error: {0}".format(err_results))
            myresults = get_ans_results(results, self.hostname)
            self.mockremote.callback.log("{0}".format(myresults))

    def build(self, pkg):

        # build the pkg passed in
        # add pkg to various lists
        # check for success/failure of build
        # return success/failure,stdout,stderr of build command
        # returns success_bool, out, err

        success = False
        build_details = {}
        self.modify_base_buildroot()

        # check if pkg is local or http
        dest = None
        if os.path.exists(pkg):
            dest = os.path.normpath(
                os.path.join(self.tempdir, os.path.basename(pkg)))

            self.conn.module_name = "copy"
            margs = "src={0} dest={1}".format(pkg, dest)
            self.conn.module_args = margs
            self.mockremote.callback.log(
                "Sending {0} to {1} to build".format(
                    os.path.basename(pkg), self.hostname))

            # FIXME should probably check this but <shrug>
            self.conn.run()
        else:
            dest = pkg

        # srpm version
        self.conn.module_name = "shell"
        self.conn.module_args = "rpm -qp --qf \"%{VERSION}\n\" "+pkg
        self.mockremote.callback.log("Getting package information: version")
        results = self.conn.run()
        if "contacted" in results:
            build_details["pkg_version"] = results["contacted"].itervalues().next()[u"stdout"]

        # construct the mockchain command
        buildcmd = "{0} -r {1} -l {2} ".format(
            mockchain, pipes.quote(self.chroot),
            pipes.quote(self.remote_build_dir))

        for r in self.repos:
            if "rawhide" in self.chroot:
                r = r.replace("$releasever", "rawhide")

            buildcmd += "-a {0} ".format(pipes.quote(r))

        if self.mockremote.macros:
            for k, v in self.mockremote.macros.items():
                mock_opt = "--define={0} {1}".format(k, v)
                buildcmd += "-m {0} ".format(pipes.quote(mock_opt))

        buildcmd += dest

        # run the mockchain command async
        self.mockremote.callback.log("executing: {0}".format(buildcmd))
        self.conn.module_name = "shell"
        self.conn.module_args = buildcmd

        _, poller = self.conn.run_async(self.timeout)

        waited = 0
        while True:
            results = poller.poll()

            if results["contacted"] or results["dark"]:
                break

            if waited >= self.timeout:
                self.mockremote.callback.log("Build timeout expired.")
                return False, "", "Timeout expired", build_details

            time.sleep(10)
            waited += 10

        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0],
            return_on_error=["stdout", "stderr"])

        if is_err:
            return (success, err_results.get("stdout", ""),
                    err_results.get("stderr", ""), build_details)

        # we know the command ended successfully but not if the pkg built
        # successfully
        myresults = get_ans_results(results, self.hostname)
        out = myresults.get("stdout", "")
        err = myresults.get("stderr", "")

        successfile = os.path.join(self._get_remote_pkg_dir(pkg), "success")
        testcmd = "/usr/bin/test -f {0}".format(successfile)
        self.conn.module_name = "shell"
        self.conn.module_args = testcmd
        results = self.conn.run()
        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0])

        if not is_err:
            success = True

            self.mockremote.callback.log("Listing built binary packages")
            self.conn.module_name = "shell"
            self.conn.module_args = \
              "cd {0} && for f in `ls *.rpm | grep -v \"src.rpm$\"`; do rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; done".format(
              pipes.quote(self._get_remote_pkg_dir(pkg)))
            results = self.conn.run()
            build_details["built_packages"] = results["contacted"].itervalues().next()[u"stdout"]
            self.mockremote.callback.log("Packages:\n"+build_details["built_packages"])


        return success, out, err, build_details

    def download(self, pkg, destdir):
        # download the pkg to destdir using rsync + ssh
        # return success/failure, stdout, stderr

        success = False
        rpd = self._get_remote_pkg_dir(pkg)
        # make spaces work w/our rsync command below :(
        destdir = "'" + destdir.replace("'", "'\\''") + "'"
        # build rsync command line from the above
        remote_src = "{0}@{1}:{2}".format(self.username, self.hostname, rpd)
        ssh_opts = "'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
        command = "{0} -avH -e {1} {2} {3}/".format(
            rsync, ssh_opts, remote_src, destdir)

        cmd = subprocess.Popen(command, shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # rsync results into opts.destdir
        out, err = cmd.communicate()
        if cmd.returncode:
            success = False
        else:
            success = True

        return success, out, err

    def check(self):
        # do check of host
        # set checked if successful
        # return success/failure, errorlist

        if self.checked:
            return True, []

        errors = []

        try:
            socket.gethostbyname(self.hostname)
        except socket.gaierror:
            raise BuilderError("{0} could not be resolved".format(
                self.hostname))

        self.conn.module_name = "shell"
        self.conn.module_args = "/bin/rpm -q mock rsync"
        res = self.conn.run()

        # check for mock/rsync from results
        is_err, err_results = check_for_ans_error(
            res, self.hostname, success_codes=[0])

        if is_err:
            if "rc" in err_results:
                errors.append(
                    "Warning: {0} does not have mock or rsync installed"
                    .format(self.hostname))
            else:
                errors.append(err_results["msg"])

        # test for path existence for mockchain and chroot config for this
        # chroot
        self.conn.module_name = "shell"
        self.conn.module_args = "/usr/bin/test -f {0}" \
            " && /usr/bin/test -f /etc/mock/{1}.cfg".format(
                mockchain, self.chroot)
        res = self.conn.run()

        is_err, err_results = check_for_ans_error(
            res, self.hostname, success_codes=[0])

        if is_err:
            if "rc" in err_results:
                errors.append(
                    "Warning: {0} lacks mockchain on chroot {1}".format(
                        self.hostname, self.chroot))
            else:
                errors.append(err_results["msg"])

        if not errors:
            self.checked = True
        else:
            msg = "\n".join(errors)
            raise BuilderError(msg)


def get_target_dir(chroot_dir, pkg_name):
    source_basename = os.path.basename(pkg_name).replace(".src.rpm", "")
    return os.path.join(chroot_dir, source_basename)


class MockRemote(object):

    def __init__(self, builder=None, user=DEF_USER, timeout=DEF_TIMEOUT,
                 destdir=DEF_DESTDIR, chroot=DEF_CHROOT, cont=False,
                 recurse=False, repos=None, callback=None,
                 remote_basedir=DEF_REMOTE_BASEDIR, remote_tempdir=None,
                 macros=None, lock=None, do_sign=False, build_id=None,
                 buildroot_pkgs=DEF_BUILDROOT_PKGS):
        """

        :param builder: builder hostname
        :param user: user to run as/connect as on builder systems
        :param timeout: ssh timeout
        :param destdir: target directory to put built packages
        :param chroot: chroot config name/base to use in the mock build
                       (e.g.: fedora20_i386 )
        :param cont: if a pkg fails to build, continue to the next one
        :param bool recurse: if more than one pkg and it fails to build,
                             try to build the rest and come back to it
        :param repos: additional repositories for mock
        :param DefaultCallBack callback: object with hooks for notifications
                                         about build progress
        :param remote_basedir: basedir on builder
        :param remote_tempdir: tempdir on builder
        :param macros: {    "copr_username": ...,
                            "copr_projectname": ...,
                            "vendor": ...}
        :param multiprocessing.Lock lock: instance of Lock shared between
            Copr backend process
        :param bool do_sign: enable package signing, require configured
            signer host and correct /etc/sign.conf
        :param buildroot_pkgs: whitespace separated string with additional
                               packages that should present during build
        """

        if repos is None:
            repos = DEF_REPOS
        if macros is None:
            macros = DEF_MACROS
        self.destdir = destdir
        self.chroot = chroot
        self.repos = repos
        self.cont = cont
        self.recurse = recurse
        self.callback = callback
        self.remote_basedir = remote_basedir
        self.remote_tempdir = remote_tempdir
        self.macros = macros
        self.lock = lock
        self.do_sign = do_sign

        if not self.callback:
            self.callback = DefaultCallBack()

        self.callback.log("Setting up builder: {0}".format(builder))
        self.builder = Builder(builder, user, timeout, self, buildroot_pkgs)

        if not self.chroot:
            raise MockRemoteError("No chroot specified!")

        self.failed = []
        self.finished = []
        self.pkg_list = []
        self.callback.log("self dict: {}".format(self.__dict__))

    def _get_pkg_destpath(self, pkg):
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace(".src.rpm", "")
        resdir = "{0}/{1}/{2}".format(self.destdir, self.chroot, pdn)
        resdir = os.path.normpath(resdir)
        return resdir

    def add_pubkey(self, chroot_dir):
        """
            Adds pubkey.gpg with public key to ``chroot_dir``
            using `copr_username` and `copr_projectname` from self.macros.
        """
        self.callback.log("Retrieving pubkey ")
        # TODO: sign repodata as well ?
        user = self.macros["copr_username"]
        project = self.macros["copr_projectname"]
        pubkey_path = os.path.join(chroot_dir, "pubkey.gpg")
        try:
            #TODO: uncomment this when key revoke/change will be implemented
            #if os.path.exists(pubkey_path):
            #    return

            get_pubkey(user, project, pubkey_path)
            self.callback.log(
                "Added pubkey for user {} project {} into the directory: {}".
                format(user, project, chroot_dir))

        except Exception as e:
            self.callback.error(
                "failed to retrieve pubkey for user {} project {} due to: \n"
                "{}".format(user, project, e))

    def sign_built_packages(self, chroot_dir, pkg):
        """
            Sign built rpms
             using `copr_username` and `copr_projectname` from self.macros
             by means of obs-sign. If user builds doesn't have a key pair
             at sign service, it would be created through ``copr-keygen``

        :param chroot_dir: Directory with rpms to be signed
        :param pkg: path to the source package

        """
        #source_basename = os.path.basename(pkg).replace(".src.rpm", "")
        self.callback.log("Going to sign pkgs from source: {} in chroot: {}".
                          format(pkg, chroot_dir))

        try:
            sign_rpms_in_dir(self.macros["copr_username"],
                             self.macros["copr_projectname"],
                             #os.path.join(chroot_dir, source_basename),
                             get_target_dir(chroot_dir, pkg),
                             callback=self.callback)
        except Exception as e:
            self.callback.log(
                "failed to sign packages "
                "built from `{}` with error: \n"
                "{}".format(pkg, e)
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
                r_log.write(to_err)
        fcntl.flock(r_log, fcntl.LOCK_UN)
        r_log.close()

    def build_pkgs(self, pkgs=None):

        if not pkgs:
            pkgs = self.pkg_list

        built_pkgs = []
        downloaded_pkgs = {}

        build_details = {}

        try_again = True
        to_be_built = pkgs
        while try_again:
            self.failed = []
            just_built = []
            for pkg in to_be_built:
                pkg = urllib.unquote(str(pkg))
                if pkg in just_built:
                    self.callback.log(
                        "skipping duplicate pkg in this list: {0}".format(pkg))
                    continue
                else:
                    just_built.append(pkg)

                p_path = self._get_pkg_destpath(pkg)

                # if it's marked as fail, nuke the failure and try to rebuild it
                if os.path.exists(os.path.join(p_path, "fail")):
                    os.unlink(os.path.join(p_path, "fail"))

                # off to the builder object
                # building
                self.callback.start_build(pkg)
                b_status, b_out, b_err, build_details = self.builder.build(pkg)
                self.callback.end_build(pkg)

                # downloading
                self.callback.start_download(pkg)
                # mockchain makes things with the chroot appended - so suck down
                # that pkg subdir from w/i that location
                chroot_dir = os.path.normpath(
                    os.path.join(self.destdir, self.chroot))

                d_ret, d_out, d_err = self.builder.download(pkg, chroot_dir)
                if not d_ret:
                    msg = "Failure to download {0}: {1}".format(
                        pkg, d_out + d_err)

                    if not self.cont:
                        raise MockRemoteError(msg)
                    self.callback.error(msg)

                self.callback.end_download(pkg)
                # write out whatever came from the builder call into the
                # destdir/chroot
                if not os.path.exists(chroot_dir):
                    os.makedirs(
                        os.path.join(self.destdir, self.chroot))

                self.log_to_file_safe(
                    os.path.join(chroot_dir, "mockchain.log"),
                    ["\n\n{0}\n\n".format(pkg), b_out], [b_err])

                ## adding info file with
                try:
                    with open(os.path.join(get_target_dir(chroot_dir, pkg), "build.info"), 'w') as info_file:
                        info_file.write("build_id={}\n".format(self.build_id))
                except IOError:
                    pass

                # checking where to stick stuff
                if not b_status:
                    if self.recurse:
                        self.failed.append(pkg)
                        self.callback.error(
                            "Error building {0}, will try again".format(
                                os.path.basename(pkg)))
                    else:
                        msg = "Error building {0}\nSee logs/results in {1}" \
                              .format(os.path.basename(pkg), self.destdir)

                        if not self.cont:
                            raise MockRemoteError(msg)
                        self.callback.error(msg)

                else:
                    self.callback.log("Success building {0}".format(
                                      os.path.basename(pkg)))

                    if self.do_sign:
                        self.sign_built_packages(chroot_dir, pkg)

                    built_pkgs.append(pkg)
                    # createrepo with the new pkgs
                    _, _, err = createrepo(chroot_dir, self.lock)
                    if err.strip():
                        self.callback.error(
                            "Error making local repo: {0}".format(chroot_dir))

                        self.callback.error(str(err))
                        # FIXME - maybe clean up .repodata and .olddata
                        # here?

            if self.failed:
                if len(self.failed) != len(to_be_built):
                    to_be_built = self.failed
                    try_again = True
                    self.callback.log(
                        "Trying to rebuild {0} failed pkgs".format(
                            len(self.failed)))
                else:
                    self.callback.log(
                        "Tried twice - following pkgs could not be"
                        " successfully built:")

                    for pkg in self.failed:
                        msg = pkg
                        if pkg in downloaded_pkgs:
                            msg = downloaded_pkgs[pkg]
                        self.callback.log(msg)

                    try_again = False
            else:
                try_again = False

        return build_details


def parse_args(args):

    parser = SortedOptParser(
        "mockremote -b hostname -u user -r chroot pkg pkg pkg")
    parser.add_option("-r", "--root", default=DEF_CHROOT, dest="chroot",
                      help="chroot config name/base to use in the mock build")
    parser.add_option("-c", "--continue", default=False, action="store_true",
                      dest="cont",
                      help="if a pkg fails to build, continue to the next one")
    parser.add_option("-a", "--addrepo", default=DEF_REPOS, action="append",
                      dest="repos",
                      help="add these repo baseurls to the chroot's yum config")
    parser.add_option("--recurse", default=False, action="store_true",
                      help="if more than one pkg and it fails to build,"
                      " try to build the rest and come back to it")
    parser.add_option("--log", default=None, dest="logfile",
                      help="log to the file named by this option,"
                      " defaults to not logging")
    parser.add_option("-b", "--builder", dest="builder", default=None,
                      help="builder to use")
    parser.add_option("-u", dest="user", default=DEF_USER,
                      help="user to run as/connect as on builder systems")
    parser.add_option("-t", "--timeout", dest="timeout", type="int",
                      default=DEF_TIMEOUT,
                      help="maximum time in seconds a build can take to run")
    parser.add_option("--destdir", dest="destdir", default=DEF_DESTDIR,
                      help="place to download all the results/packages")
    parser.add_option("--packages", dest="packages_file", default=None,
                      help="file to read list of packages from")
    parser.add_option("--do-sign", dest="do_sign", default=False,
                      help="enable package signing")
    parser.add_option("-q", "--quiet", dest="quiet", default=False,
                      action="store_true",
                      help="output very little to the terminal")

    opts, args = parser.parse_args(args)

    if not opts.builder:
        sys.stderr.write("Must specify a system to build on")
        sys.exit(1)

    if opts.packages_file and os.path.exists(opts.packages_file):
        args.extend(read_list_from_file(opts.packages_file))

    # args = list(set(args)) # poor man's 'unique' - this also changes the order
    # :(

    if not args:
        sys.stderr.write("Must specify at least one pkg to build")
        sys.exit(1)

    if not opts.chroot:
        sys.stderr.write("Must specify a mock chroot")
        sys.exit(1)

    for url in opts.repos:
        if not (url.startswith("http://") or
                url.startswith("https://") or url.startswith("file://")):

            sys.stderr.write("Only http[s] or file urls allowed for repos")
            sys.exit(1)

    return opts, args


# FIXME
# play with createrepo run at the end of each build
# need to output the things that actually worked :)


def main(args):

    # parse args
    opts, pkgs = parse_args(args)

    if not os.path.exists(opts.destdir):
        os.makedirs(opts.destdir)

    try:
        # setup our callback
        callback = CliLogCallBack(logfn=opts.logfile, quiet=opts.quiet)
        # our mockremote instance
        mr = MockRemote(builder=opts.builder,
                        user=opts.user,
                        timeout=opts.timeout,
                        destdir=opts.destdir,
                        chroot=opts.chroot,
                        cont=opts.cont,
                        recurse=opts.recurse,
                        repos=opts.repos,
                        do_sign=opts.do_sign,
                        callback=callback,)

        # FIXMES
        # things to think about doing:
        # output the remote tempdir when you start up
        # output the number of pkgs
        # output where you're writing things to
        # consider option to sync over destdir to the remote system to use
        # as a local repo for the build
        #

        if not opts.quiet:
            print("Building {0} pkgs".format(len(pkgs)))

        mr.build_pkgs(pkgs)

        if not opts.quiet:
            print("Output written to: {0}".format(mr.destdir))

    except MockRemoteError as e:
        sys.stderr.write("Error on build:\n")
        sys.stderr.write("{0}\n".format(e))
        return


if __name__ == "__main__":
    main(sys.argv[1:])
