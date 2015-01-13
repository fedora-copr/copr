import os
import pipes
import socket
from subprocess import Popen, PIPE
import time

from ansible.runner import Runner

# from ..exceptions import BuilderError, BuilderTimeOutError, AnsibleCallError, AnsibleResponseError
from backend.exceptions import BuilderError, BuilderTimeOutError, AnsibleCallError, AnsibleResponseError

# from ..constants import mockchain, rsync
from backend.constants import mockchain, rsync


class Builder(object):

    def __init__(self, opts, hostname, username, job,
                 timeout, chroot, buildroot_pkgs,
                 callback,
                 remote_basedir, remote_tempdir=None,
                 macros=None, repos=None):

        # TODO: remove fields obtained from opts
        self.opts = opts
        self.hostname = hostname
        self.username = username
        self.job = job
        self.timeout = timeout
        self.chroot = chroot
        self.repos = repos or []
        self.macros = macros or {}  # rename macros to mock_ext_options
        self.callback = callback

        self.buildroot_pkgs = buildroot_pkgs or ""

        self._remote_tempdir = remote_tempdir
        self._remote_basedir = remote_basedir
        # if we're at this point we've connected and done stuff on the host
        self.conn = self._create_ans_conn()
        self.root_conn = self._create_ans_conn(username="root")

        # self.callback.log("Created builder: {}".format(self.__dict__))

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

    def _create_ans_conn(self, username=None):
        ans_conn = Runner(remote_user=username or self.username,
                          host_list=self.hostname + ",",
                          pattern=self.hostname,
                          forks=1,
                          transport=self.opts.ssh.transport,
                          timeout=self.timeout)
        return ans_conn

    def run_ansible_with_check(self, cmd, module_name=None, as_root=False,
                               err_codes=None, success_codes=None):

        results = self._run_ansible(cmd, module_name, as_root)

        try:
            check_for_ans_error(
                results, self.hostname, err_codes, success_codes)
        except AnsibleResponseError as response_error:
            raise AnsibleCallError(
                msg="Failed to execute ansible command",
                cmd=cmd, module_name=module_name, as_root=as_root,
                return_code=response_error.return_code,
                stdout=response_error.stdout, stderr=response_error.stderr
            )

        return results

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

    def modify_mock_chroot_config(self):
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

        kwargs = {
            "chroot": self.chroot,
            "pkgs": self.buildroot_pkgs
        }
        buildroot_cmd = (
            "dest=/etc/mock/{chroot}.cfg"
            " line=\"config_opts['chroot_setup_cmd'] = 'install @buildsys-build {pkgs}'\""
            " regexp=\"^.*chroot_setup_cmd.*$\""
        )

        disable_networking_cmd = (
            "dest=/etc/mock/{chroot}.cfg"
            " line=\"config_opts['use_host_resolv'] = False\""
            " regexp=\"^.*user_host_resolv.*$\""
        )
        try:
            self.run_ansible_with_check(buildroot_cmd.format(**kwargs),
                                        module_name="lineinfile", as_root=True)
            if not self.job.enable_net:
                self.run_ansible_with_check(disable_networking_cmd.format(**kwargs),
                                            module_name="lineinfile", as_root=True)
        except BuilderError as err:
            self.callback.log(str(err))
            raise


        # results = self._run_ansible(
        #     "dest=/etc/mock/{0}.cfg"
        #     " line=\"config_opts['chroot_setup_cmd'] = 'install @buildsys-build {1}'\""
        #     " regexp=\"^.*chroot_setup_cmd.*$\""
        #     .format(self.chroot, self.buildroot_pkgs),
        #     module_name="lineinfile", as_root=True)
        #
        # is_err, err_results = check_for_ans_error(results, self.hostname)
        #
        # if is_err:
        #     self.callback.log("Error: {0}".format(err_results))
        #     myresults = get_ans_results(results, self.hostname)
        #     self.callback.log("{0}".format(myresults))

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

    def check_build_success(self, pkg):
        successfile = os.path.join(self._get_remote_pkg_dir(pkg), "success")
        ansible_test_results = self._run_ansible("/usr/bin/test -f {0}".format(successfile))
        # is_err, err_results = check_for_ans_error(ansible_test_results, self.hostname)
        check_for_ans_error(ansible_test_results, self.hostname)
        # return err, is_err, out
        #return out

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
                msg = "Build timeout expired. Time limit: {}s, time spent: {}s".format(
                    self.timeout, waited)
                self.callback.log(msg)
                raise BuilderTimeOutError(msg)

            time.sleep(10)
            waited += 10
        return results

    def build(self, pkg):
        # build the pkg passed in
        # add pkg to various lists
        # check for success/failure of build

        build_details = {}
        self.modify_mock_chroot_config()

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
        ansible_build_results = self.run_command_and_wait(buildcmd)  # now raises BuildTimeoutError
        # try:
        # except BuilderTimeOutError:
        #     return False, "", "Timeout expired", build_details
        check_for_ans_error(ansible_build_results, self.hostname)  # on error raises AnsibleResponseError
        # is_err, err_results = check_for_ans_error(ansible_build_results, self.hostname)
        # if is_err:
        #     return (False, err_results.get("stdout", ""),
        #             err_results.get("stderr", ""), build_details)

        # we know the command ended successfully but not if the pkg built
        # successfully
        self.check_build_success(pkg)
        build_out = get_ans_results(ansible_build_results, self.hostname).get("stdout", "")

        # success = False
        # if not is_err:
        #     success = True
        self.collect_built_packages(build_details, pkg)
        return build_details, build_out
        # return success, out, err, build_details

    def download(self, pkg, destdir):
            # download the pkg to destdir using rsync + ssh

        rpd = self._get_remote_pkg_dir(pkg)
        # make spaces work w/our rsync command below :(
        destdir = "'" + destdir.replace("'", "'\\''") + "'"

        # build rsync command line from the above
        remote_src = "{0}@{1}:{2}".format(self.username, self.hostname, rpd)
        ssh_opts = "'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"

        stdout_filepath = os.path.join(destdir, "build-{}.rsync_out.log".format(self.job.build_id))
        stderr_filepath = os.path.join(destdir, "build-{}.rsync_err.log".format(self.job.build_id))

        command = "{} -avH -e {} {} {}/ > {} 2> {}".format(
            rsync, ssh_opts, remote_src, destdir,
            stdout_filepath, stderr_filepath)


        # dirty magic with Popen due to IO buffering
        # see http://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
        # alternative: use tempfile.Tempfile as Popen stdout/stderr

        try:
            cmd = Popen(command, shell=True)
            cmd.wait()
        except Exception as error:
            raise BuilderError(msg="Failed to download from builder due to rsync error, "
                                   "see logs dir. Original error: {}".format(error))
        if cmd.returncode != 0:
            raise BuilderError(msg="Failed to download from builder due to rsync error, "
                                   "see logs dir. Rsync return_code={}".format(cmd.returncode))

    def check(self):
        # do check of host

        # errors = []

        try:
            socket.gethostbyname(self.hostname)
        except socket.gaierror:
            raise BuilderError("{0} could not be resolved".format(
                self.hostname))

        # res = self._run_ansible("/bin/rpm -q mock rsync")
        # check for mock/rsync from results
        # is_err, err_results = check_for_ans_error(res, self.hostname)
        #
        # if is_err:
        #     if "rc" in err_results:
        #         errors.append(
        #             "Warning: {0} does not have mock or rsync installed"
        #             .format(self.hostname))
        #     else:
        #         errors.append(err_results["msg"])
        try:
            # check_for_ans_error(res, self.hostname)
            self.run_ansible_with_check("/bin/rpm -q mock rsync")
        except AnsibleCallError:
            raise BuilderError(msg="Build host `{0}` does not have mock or rsync installed"
                               .format(self.hostname))

        # test for path existence for mockchain and chroot config for this
        # chroot

        # res = self._run_ansible(
        #     "/usr/bin/test -f {}"
        #     " && /usr/bin/test -f /etc/mock/{}.cfg"
        #     .format(mockchain, self.chroot))
        #
        try:
            self.run_ansible_with_check("/usr/bin/test -f {0}".format(mockchain))
        except AnsibleCallError:
            raise BuilderError(msg="Build host `{}` missing mockchain binary `{}`"
                               .format(self.hostname, mockchain))

        try:
            self.run_ansible_with_check("/usr/bin/test -f /etc/mock/{}.cfg"
                                        .format(self.chroot))
        except AnsibleCallError:
            raise BuilderError(msg="Build host `{}` missing mock config for chroot `{}`"
                               .format(self.hostname, self.chroot))


        # is_err, err_results = check_for_ans_error(res, self.hostname)
        #
        # if is_err:
        #     if "rc" in err_results:
        #         errors.append(
        #             "Warning: {0} lacks mockchain binary or mock config for chroot {1}".format(
        #                 self.hostname, self.chroot))
        #     else:
        #         errors.append(err_results["msg"])
        #
        # if not errors:
        #     self.checked = True
        # else:
        #     msg = "\n".join(errors)
        #     raise BuilderError(msg)


def get_ans_results(results, hostname):
    if hostname in results["dark"]:
        return results["dark"][hostname]
    if hostname in results["contacted"]:
        return results["contacted"][hostname]

    return {}


def check_for_ans_error(results, hostname, err_codes=None, success_codes=None):
    """
    dict includes 'msg'
    may include 'rc', 'stderr', 'stdout' and any other requested result codes

    :raises AnsibleResponseError:
    """

    if err_codes is None:
        err_codes = []
    if success_codes is None:
        success_codes = [0]

    if "dark" in results and hostname in results["dark"]:
        # err_results["msg"] = "Error: Could not contact/connect" \
        #     " to {0}.".format(hostname)
        #
        # return True, err_results
        raise AnsibleResponseError(
            msg="Error: Could not contact/connect to {}.".format(hostname))

    error = False
    err_results = {}
    if err_codes or success_codes:
        if hostname in results["contacted"]:
            if "rc" in results["contacted"][hostname]:
                rc = int(results["contacted"][hostname]["rc"])
                err_results["return_code"] = rc
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
            for item in ["stdout", "stderr"]:
                if item in results["contacted"][hostname]:
                    err_results[item] = results["contacted"][hostname][item]

    if error:
        raise AnsibleResponseError(**err_results)
    # return error, err_results
