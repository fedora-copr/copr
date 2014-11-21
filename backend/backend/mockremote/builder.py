import os
import pipes
import socket
from subprocess import Popen, PIPE
import time

from ansible.runner import Runner

from ..exceptions import BuilderError, BuilderTimeOutError

from ..constants import mockchain, rsync


class Builder(object):

    def __init__(self, hostname, username,
                 timeout, chroot, buildroot_pkgs,
                 callback,
                 remote_basedir, remote_tempdir=None,
                 macros=None, repos=None):

        self.hostname = hostname
        self.username = username
        self.timeout = timeout
        self.chroot = chroot
        self.repos = repos or []
        self.macros = macros or {}  # rename macros to mock_ext_options
        self.callback = callback

        self.buildroot_pkgs = buildroot_pkgs or ""

        self.checked = False
        self._remote_tempdir = remote_tempdir
        self._remote_basedir = remote_basedir
        # if we're at this point we've connected and done stuff on the host
        self.conn = _create_ans_conn(
            self.hostname, self.username, self.timeout)
        self.root_conn = _create_ans_conn(self.hostname, "root", self.timeout)

        self.callback.log("Created builder: {}".format(self.__dict__))

        # Before use: check out the host - make sure it can build/be contacted/etc
        # self.check()

    @property
    def remote_build_dir(self):
        return self.tempdir + "/build/"

    @property
    def tempdir(self):
        if self._remote_tempdir:
            return self._remote_tempdir

        create_tmpdir_cmd = "/bin/mktemp -d {0}/{1}-XXXXX".format(
            self._remote_basedir, "mockremote")

        results = self._run_ansible(create_tmpdir_cmd)

        tempdir = None
        # TODO: use check_for_ans_error
        for _, resdict in results["contacted"].items():
            tempdir = resdict["stdout"]

        # if still nothing then we"ve broken
        if not tempdir:
            raise BuilderError("Could not make tmpdir on {0}".format(
                self.hostname))

        self._run_ansible("/bin/chmod 755 {0}".format(tempdir))
        self._remote_tempdir = tempdir

        return self._remote_tempdir

    @tempdir.setter
    def tempdir(self, value):
        self._remote_tempdir = value

    def _run_ansible(self, cmd, module_name=None, as_root=False):
        """
            Executes single ansible module

        :param str cmd: module command
        :param str module_name: name of the invoked module
        :param bool as_root:
        :return: ansible command result
        """
        if as_root:
            conn = self.root_conn
        else:
            conn = self.conn

        conn.module_name = module_name or "shell"
        conn.module_args = str(cmd)
        return conn.run()

    def _get_remote_pkg_dir(self, pkg):
        # the pkg will build into a dir by mockchain named:
        # $tempdir/build/results/$chroot/$packagename
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace(".src.rpm", "")
        remote_pkg_dir = os.path.normpath(
            os.path.join(self.remote_build_dir, "results",
                         self.chroot, pdn))

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

        self.callback.log("putting {0} into minimal buildroot of {1}"
                          .format(self.buildroot_pkgs, self.chroot))

        results = self._run_ansible(
            "dest=/etc/mock/{0}.cfg"
            " line=\"config_opts['chroot_setup_cmd'] = 'install @buildsys-build {1}'\""
            " regexp=\"^.*chroot_setup_cmd.*$\""
            .format(self.chroot, self.buildroot_pkgs),
            module_name="lineinfile", as_root=True)

        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0],
            return_on_error=["stdout", "stderr"])

        if is_err:
            self.callback.log("Error: {0}".format(err_results))
            myresults = get_ans_results(results, self.hostname)
            self.callback.log("{0}".format(myresults))

    def collect_built_packages(self, build_details, pkg):
        self.callback.log("Listing built binary packages")
        # self.conn.module_name = "shell"

        results = self._run_ansible(
            "cd {0} && "
            "for f in `ls *.rpm |grep -v \"src.rpm$\"`; do"
            "   rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(pipes.quote(self._get_remote_pkg_dir(pkg)))
        )

        build_details["built_packages"] = list(results["contacted"].values())[0][u"stdout"]
        self.callback.log("Packages:\n{}".format(build_details["built_packages"]))

    def check_build_success(self, pkg, results):
        myresults = get_ans_results(results, self.hostname)
        out = myresults.get("stdout", "")
        err = myresults.get("stderr", "")
        successfile = os.path.join(self._get_remote_pkg_dir(pkg), "success")
        results = self._run_ansible("/usr/bin/test -f {0}".format(successfile))
        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0])
        return err, is_err, out

    def check_if_pkg_local_or_http(self, pkg):
        """
            Local file will be sent into the build chroot,
            if pkg is a url, it will be returned as is.

            :param str pkg: path to the local file or URL
            :return str: fixed pkg location
        """
        if os.path.exists(pkg):
            dest = os.path.normpath(
                os.path.join(self.tempdir, os.path.basename(pkg)))

            self.callback.log(
                "Sending {0} to {1} to build".format(
                    os.path.basename(pkg), self.hostname))

            # FIXME should probably check this but <shrug>
            self._run_ansible("src={0} dest={1}".format(pkg, dest), module_name="copy")
        else:
            dest = pkg

        return dest

    def get_package_version(self, pkg):
        self.callback.log("Getting package information: version")
        results = self._run_ansible("rpm -qp --qf \"%{{VERSION}}\" {}".format(pkg))
        if "contacted" in results:
            # TODO:  do more sane
            return list(results["contacted"].values())[0][u"stdout"]
        else:
            return None

    def gen_mockchain_command(self, dest):
        buildcmd = "{0} -r {1} -l {2} ".format(
            mockchain, pipes.quote(self.chroot),
            pipes.quote(self.remote_build_dir))
        for r in self.repos:
            if "rawhide" in self.chroot:
                r = r.replace("$releasever", "rawhide")

            buildcmd += "-a {0} ".format(pipes.quote(r))
        for k, v in self.macros.items():
            mock_opt = "--define={0} {1}".format(k, v)
            buildcmd += "-m {0} ".format(pipes.quote(mock_opt))
        buildcmd += dest
        return buildcmd

    def run_command_and_wait(self, buildcmd):
        self.callback.log("executing: {0}".format(buildcmd))
        self.conn.module_name = "shell"
        self.conn.module_args = buildcmd
        _, poller = self.conn.run_async(self.timeout)
        waited = 0
        results = None
        while True:
            # TODO: try replace with ``while waited < self.timeout``
            # extract method and return waited time, raise timeout error in `else`
            results = poller.poll()

            if results["contacted"] or results["dark"]:
                break

            if waited >= self.timeout:
                self.callback.log("Build timeout expired.")
                #return False, "", "Timeout expired", build_details
                raise BuilderTimeOutError("Build timeout expired.")

            time.sleep(10)
            waited += 10
        return results

    def build(self, pkg):
        # build the pkg passed in
        # add pkg to various lists
        # check for success/failure of build
        # return success/failure,stdout,stderr of build command
        # returns success_bool, out, err

        build_details = {}
        self.modify_base_buildroot()

        # check if pkg is local or http
        dest = self.check_if_pkg_local_or_http(pkg)

        # srpm version
        srpm_version = self.get_package_version(pkg)
        if srpm_version:
            # TODO: do we really need this check? maybe := None is also OK?
            build_details["pkg_version"] = srpm_version

        # construct the mockchain command
        buildcmd = self.gen_mockchain_command(dest)

        # run the mockchain command async
        try:
            results = self.run_command_and_wait(buildcmd)
        except BuilderTimeOutError:
            return False, "", "Timeout expired", build_details

        is_err, err_results = check_for_ans_error(
            results, self.hostname, success_codes=[0],
            return_on_error=["stdout", "stderr"])

        if is_err:
            return (False, err_results.get("stdout", ""),
                    err_results.get("stderr", ""), build_details)

        # we know the command ended successfully but not if the pkg built
        # successfully
        err, is_err, out = self.check_build_success(pkg, results)
        success = False
        if not is_err:
            success = True
            self.collect_built_packages(build_details, pkg)

        return success, out, err, build_details

    def download(self, pkg, destdir):
        # download the pkg to destdir using rsync + ssh
        # return success/failure, stdout, stderr

        rpd = self._get_remote_pkg_dir(pkg)
        # make spaces work w/our rsync command below :(
        destdir = "'" + destdir.replace("'", "'\\''") + "'"
        # build rsync command line from the above
        remote_src = "{0}@{1}:{2}".format(self.username, self.hostname, rpd)
        ssh_opts = "'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
        command = "{0} -avH -e {1} {2} {3}/".format(
            rsync, ssh_opts, remote_src, destdir)

        cmd = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)

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

        res = self._run_ansible("/bin/rpm -q mock rsync")
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

        res = self._run_ansible(
            "/usr/bin/test -f {0}"
            " && /usr/bin/test -f /etc/mock/{1}.cfg"
            .format(mockchain, self.chroot))

        is_err, err_results = check_for_ans_error(
            res, self.hostname, success_codes=[0])

        if is_err:
            if "rc" in err_results:
                errors.append(
                    "Warning: {0} lacks mockchain binary or mock config for chroot {1}".format(
                        self.hostname, self.chroot))
            else:
                errors.append(err_results["msg"])

        if not errors:
            self.checked = True
        else:
            msg = "\n".join(errors)
            raise BuilderError(msg)


def _create_ans_conn(hostname, username, timeout):
    ans_conn = Runner(remote_user=username,
                      host_list=hostname + ",",
                      pattern=hostname,
                      forks=1,
                      transport="ssh",
                      timeout=timeout)
    return ans_conn


def get_ans_results(results, hostname):
    if hostname in results["dark"]:
        return results["dark"][hostname]
    if hostname in results["contacted"]:
        return results["contacted"][hostname]

    return {}


def check_for_ans_error(results, hostname, err_codes=None, success_codes=None,
                        return_on_error=None):
    """
    dict includes 'msg'
    may include 'rc', 'stderr', 'stdout' and any other requested result codes

    :return tuple: (True or False, dict)
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
