import os
import pipes
import socket
from subprocess import Popen
import time
from urlparse import urlparse
import glob

from backend.vm_manage import PUBSUB_INTERRUPT_BUILDER
from ..helpers import get_redis_connection, ensure_dir_exists

from ..exceptions import BuilderError, BuilderTimeOutError, RemoteCmdError, VmError

from ..constants import mockchain, rsync, DEF_BUILD_TIMEOUT
from ..sshcmd import SSHConnectionError, SSHConnection

import modulemd


class Builder(object):

    def __init__(self, opts, hostname, job, logger):

        self.opts = opts
        self.hostname = hostname
        self.job = job
        self.timeout = self.job.timeout or self.opts.timeout
        self.repos =  []
        self.log = logger

        self.buildroot_pkgs = self.job.buildroot_pkgs or ""
        self._remote_tempdir = self.opts.remote_tempdir
        self._remote_basedir = self.opts.remote_basedir
        self._remote_pkg_path = None

        self.root_conn = SSHConnection(host=self.hostname, config_file=self.opts.ssh.builder_config)
        self.conn = SSHConnection(user=self.opts.build_user, host=self.hostname, config_file=self.opts.ssh.builder_config)

        self.module_dist_tag = self._load_module_dist_tag()
        self._build_pid = None

    def _load_module_dist_tag(self):
        module_md_filepath = os.path.join(self.job.destdir, self.job.chroot, "module_md.yaml")
        try:
            mmd = modulemd.ModuleMetadata()
            mmd.load(module_md_filepath)
            dist_tag = ("." + mmd.name + '+' + mmd.stream + '+' + str(mmd.version))
        except IOError as e:
            return None
        except Exception as e:
            self.log.exception(str(e))
            return None
        else:
            self.log.info("Loaded {}, dist_tag {}".format(module_md_filepath, dist_tag))
        return dist_tag

    def get_chroot_config_path(self, chroot):
        return "{tempdir}/{chroot}.cfg".format(tempdir=self.tempdir, chroot=chroot)

    @property
    def remote_build_dir(self):
        return self.tempdir + "/build/"

    @property
    def tempdir(self):
        if self._remote_tempdir:
            return self._remote_tempdir

        if self.opts.standalone_builder:
            tempdir_path = "/var/lib/copr-builder"
        else:
            tempdir_path = "{0}/{1}-{2}".format(
                self._remote_basedir, "mockremote", self.job.task_id)
            self._run_ssh_cmd("/bin/mkdir -m 755 -p {0}".format(tempdir_path))

        self._remote_tempdir = tempdir_path
        return self._remote_tempdir

    @tempdir.setter
    def tempdir(self, value):
        self._remote_tempdir = value

    def _run_ssh_cmd(self, cmd, as_root=False):
        """
        Executes single shell command remotely

        :param str cmd: shell command
        :param bool as_root:
        :return: stdout, stderr as strings
        """
        if as_root:
            conn = self.root_conn
        else:
            conn = self.conn

        self.log.info("BUILDER CMD: "+cmd)

        rc, out, err = conn.run_expensive(cmd)
        if rc != 0:
            raise RemoteCmdError("Error running remote ssh command.",
                                 cmd, rc, as_root, err, out)
        return out, err

    def _get_remote_results_dir(self):
        if self.opts.standalone_builder:
            return os.path.join(self.tempdir, 'results')

        if any(x is None for x in [self.remote_build_dir,
                                   self.remote_pkg_name,
                                   self.job.chroot]):
            return None
        # the pkg will build into a dir by mockchain named:
        # $tempdir/build/results/$chroot/$packagename
        return os.path.normpath(os.path.join(
            self.remote_build_dir, "results", self.job.chroot, self.remote_pkg_name))

    def _get_remote_config_dir(self):
        return os.path.normpath(os.path.join(self.remote_build_dir, "configs", self.job.chroot))

    def setup_mock_chroot_config(self):
        """
        Setup mock config for current chroot.

        Packages in buildroot_pkgs are added to minimal buildroot.
        """
        cfg_path = self.get_chroot_config_path(self.job.chroot)
        copy_cmd = "cp /etc/mock/{chroot}.cfg {dest}".format(chroot=self.job.chroot, dest=cfg_path)
        self._run_ssh_cmd(copy_cmd)

        if ("'{0} '".format(self.buildroot_pkgs) !=
                pipes.quote(str(self.buildroot_pkgs) + ' ')):

            # just different test if it contains only alphanumeric characters
            # allowed in packages name
            raise BuilderError("Do not try this kind of attack on me")

        set_networking_cmd = "echo \"config_opts['use_host_resolv'] = {net_enabled}\" >> {path}".format(
            net_enabled=("True" if self.job.enable_net else "False"), path=cfg_path
        )
        self._run_ssh_cmd(set_networking_cmd)

        if self.buildroot_pkgs:
            if 'custom' in self.job.chroot:
                pattern = "^config_opts\['chroot_setup_cmd'\] = ''$"
                replace_by = "config_opts['chroot_setup_cmd'] = 'install {pkgs}'".format(pkgs=self.buildroot_pkgs)
                buildroot_custom_cmd = "sed -i \"s+{pattern}+{replace_by}+\" {path}".format(
                    pattern=pattern, replace_by=replace_by, path=cfg_path
                )
                self._run_ssh_cmd(buildroot_custom_cmd)
            else:
                pattern = "^.*chroot_setup_cmd.*\(@buildsys-build\|@build\|buildsys-build buildsys-macros\).*$"
                replace_by = "config_opts['chroot_setup_cmd'] = 'install \\1 {pkgs}'".format(pkgs=self.buildroot_pkgs)
                buildroot_cmd = "sed -i \"s+{pattern}+{replace_by}+\" {path}".format(
                    pattern=pattern, replace_by=replace_by, path=cfg_path
                )
                self._run_ssh_cmd(buildroot_cmd)

        if self.module_dist_tag:
            dist_tag_cmd = "echo \"config_opts['macros']['%dist'] = '{dist_tag}'\" >> {path}".format(
                dist_tag=self.module_dist_tag, path=cfg_path
            )
            self._run_ssh_cmd(dist_tag_cmd)

    def collect_built_packages(self):
        self.log.info("Listing built binary packages")
        built_packages = self._run_ssh_cmd(
            "cd {0} && "
            "for f in `ls *.rpm |grep -v \"src.rpm$\"`; do"
            "   rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(pipes.quote(self._get_remote_results_dir()))
        )[0].strip()
        self.log.info("Built packages:\n{}".format(built_packages))
        return built_packages

    def check_build_success(self):
        successfile = os.path.join(self._get_remote_results_dir(), "success")
        self._run_ssh_cmd("/usr/bin/test -f {0}".format(successfile))

    def download_job_pkg_to_builder(self):
        repo_url = "{}/{}.git".format(self.opts.dist_git_url, self.job.git_repo)
        self.log.info("Cloning Dist Git repo {}, branch {}, hash {}".format(
            self.job.git_repo, self.job.git_branch, self.job.git_hash))
        stdout, stderr = self._run_ssh_cmd(
            "rm -rf /tmp/build_package_repo && "
            "mkdir /tmp/build_package_repo && "
            "cd /tmp/build_package_repo && "
            "git clone {repo_url} && "
            "cd {pkg_name} && "
            "git checkout {git_hash} && "
            "fedpkg-copr --dist {branch} srpm"
            .format(repo_url=repo_url,
                    pkg_name=self.job.package_name,
                    git_hash=self.job.git_hash,
                    branch=self.job.git_branch))

    @property
    def remote_pkg_path(self):
        if self._remote_pkg_path:
            return self._remote_pkg_path

        try:
            remote_path_pattern = "/tmp/build_package_repo/{0}/*.src.rpm".format(self.job.package_name)
            stdout, stderr = self._run_ssh_cmd("/usr/bin/ls {0}".format(remote_path_pattern))
        except RemoteCmdError:
            return None

        self._remote_pkg_path = stdout.strip()
        return self._remote_pkg_path

    @property
    def remote_pkg_name(self):
        try:
            return os.path.basename(self.remote_pkg_path).replace(".src.rpm", "")
        except AttributeError:
            return None

    def pre_process_repo_url(self, repo_url):
        """
            Expands variables and sanitize repo url to be used for mock config
        """
        try:
            parsed_url = urlparse(repo_url)
            if parsed_url.scheme == "copr":
                user = parsed_url.netloc
                prj = parsed_url.path.split("/")[1]
                repo_url = "/".join([self.opts.results_baseurl, user, prj, self.job.chroot])

            else:
                if "rawhide" in self.job.chroot:
                    repo_url = repo_url.replace("$releasever", "rawhide")
                # custom expand variables
                repo_url = repo_url.replace("$chroot", self.job.chroot)
                repo_url = repo_url.replace("$distname", self.job.chroot.split("-")[0])

            return pipes.quote(repo_url)
        except Exception as err:
            self.log.exception("Failed to pre-process repo url: {}".format(err))
            return None

    @property
    def livelog_name(self):
        if self.opts.standalone_builder:
            return "/var/lib/copr-builder/live-log"
        return pipes.quote('/tmp/{}.log'.format(self.job.task_id))

    def run_async_build(self):
        if self.opts.standalone_builder:
            cmd = self._copr_builder_cmd()
            pid, _ = self._run_ssh_cmd(cmd)
            self._build_pid =int(pid.strip())
            return


        buildcmd = "timeout {} {} -r {} -l {} ".format(
            self.timeout, mockchain, pipes.quote(self.get_chroot_config_path(self.job.chroot)),
            pipes.quote(self.remote_build_dir))

        for repo in self.job.chroot_repos_extended:
            repo = self.pre_process_repo_url(repo)
            if repo is not None:
                buildcmd += "-a {0} ".format(repo)

        for k, v in self.job.mockchain_macros.items():
            mock_opt = "--define={} {}".format(k, v)
            buildcmd += "-m {} ".format(pipes.quote(mock_opt))

        buildcmd += self.remote_pkg_path

        # To run something on background, we need to:
        # - ignore SIGHUP, 'nohup' is racy -> sighup'ed by ssh before signal
        #   handler is actually set by nohup
        # - make sure to not have attached std{out,err} descriptors to the pty
        #   provided by 'ssh -t' (redirect or close them!); otherwise 'ssh -t'
        #   hangs here till the command finishes, OTOH ...
        # - doing &>{livelog} means that the mockchain command has no terminal
        #   on std{out,err} which means that it's output are not line-buffered
        #   (which wouldn't be very useful live-log), so let's use `unbuffer`
        #   from expect.rpm to allocate _persistent_ server-side pseudo-terminal
        buildcmd_async = 'trap "" SIGHUP; unbuffer {buildcmd} &>{livelog} & echo $!'.format(
            livelog=self.livelog_name, buildcmd=buildcmd)
        pid, _ = self._run_ssh_cmd(buildcmd_async)
        self._build_pid =int(pid.strip())

    def setup_pubsub_handler(self):

        self.rc = get_redis_connection(self.opts)
        self.ps = self.rc.pubsub(ignore_subscribe_messages=True)
        channel_name = PUBSUB_INTERRUPT_BUILDER.format(self.hostname)
        self.ps.subscribe(channel_name)

        self.log.info("Subscribed to vm interruptions channel {}".format(channel_name))

    def check_pubsub(self):
        # self.log.info("Checking pubsub channel")
        msg = self.ps.get_message()
        if msg is not None and msg.get("type") == "message":
            raise VmError("Build interrupted by msg: {}".format(msg["data"]))

    # def start_build(self, pkg):
    #     # build the pkg passed in
    #     # add pkg to various lists
    #     # check for success/failure of build
    #
    #     # build_details = {}
    #     self.setup_mock_chroot_config()
    #
    #     # check if pkg is local or http
    #     dest = self.check_if_pkg_local_or_http(pkg)
    #
    #     # srpm version
    #     self.update_job_pkg_version(pkg)
    #
    #     # construct the mockchain command
    #     buildcmd = self.gen_mockchain_command(dest)
    #

    @property
    def build_pid(self):
        if self._build_pid:
            return self._build_pid
        try:
            pidof_cmd = "/usr/bin/pgrep -o -u {user} {command}".format(
                user=self.opts.build_user, command="mockchain")

            if self.opts.standalone_builder:
                pidof_cmd = "cat /var/lib/copr-builder/pid"

            out, _ = self._run_ssh_cmd(pidof_cmd)
        except:
            return None

        return int(out.strip())


    def _copr_builder_cmd(self):
        template = 'copr-builder --config {config} --copr {copr} ' \
                 + '--package {package} --revision {revision} ' \
                 + '--host-resolv {net} --timeout {timeout} ' \
                 + '--chroot {chroot} --detached '

        # Repo name like <user/group>/<copr>/<package>
        git_repo_path = self.job.git_repo.split('/')

        copr = '{0}/{1}'.format(git_repo_path[0], git_repo_path[1])
        package = git_repo_path[2]

        return template.format(
            config=self.opts.standalone_builder_config,
            copr=copr,
            package=package,
            revision=self.job.git_hash,
            net="True" if self.job.enable_net else "False",
            chroot=self.job.chroot,
            timeout=self.timeout,
        )

    def attach_to_build(self):
        if not self.build_pid:
            self.log.info("Build is not running. Continuing...")
            return

        ensure_dir_exists(self.job.results_dir, self.log)
        live_log = os.path.join(self.job.results_dir, 'mockchain-live.log')

        live_cmd = '/usr/bin/tail -n +0 -f --pid={pid} {log}'.format(
            pid=self.build_pid, log=self.livelog_name)

        self.log.info("Attaching to live build log: " + live_cmd)
        with open(live_log, 'w') as logfile:
            # Ignore the exit status.
            self.conn.run(live_cmd, stdout=logfile, stderr=logfile)


    def build(self):
        if not self.opts.standalone_builder:
            # make mock config
            self.setup_mock_chroot_config()

            # download the package to the builder
            self.download_job_pkg_to_builder()

        # run the build
        self.run_async_build()

        # attach to building output
        self.attach_to_build()

    def reattach(self):
        self.attach_to_build()

    def rsync_call(self, source_path, target_path):
        ensure_dir_exists(target_path, self.log)

        # make spaces work w/our rsync command below :(
        target_path = "'" + target_path.replace("'", "'\\''") + "'"

        ssh_opts = "'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
        full_source_path = "{}@{}:{}/*".format(self.opts.build_user,
                                               self.hostname,
                                               source_path)
        log_filepath = os.path.join(target_path, self.job.rsync_log_name)
        command = "{} -rlptDvH -e {} {} {}/ &> {}".format(
            rsync, ssh_opts, full_source_path, target_path, log_filepath)

        # dirty magic with Popen due to IO buffering
        # see http://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
        # alternative: use tempfile.Tempfile as Popen stdout/stderr
        try:
            self.log.info("rsyncing of {0} started for job: {1}".format(full_source_path, self.job))
            cmd = Popen(command, shell=True)
            cmd.wait()
            self.log.info("rsyncing finished.")
        except Exception as error:
            err_msg = "Failed to download data from builder due to rsync error, see the rsync log file for details. Original error: {}".format(error)
            self.log.error(err_msg)
            raise BuilderError(err_msg)

        if cmd.returncode != 0:
            err_msg = "Failed to download data from builder due to rsync error, see the rsync log file for details."
            self.log.error(err_msg)
            raise BuilderError(err_msg)

    def download_results(self, target_path):
        if self._get_remote_results_dir():
            self.rsync_call(self._get_remote_results_dir(), target_path)

    def download_configs(self, target_path):
        self.rsync_call(self._get_remote_config_dir(), target_path)

    def check(self):
        if self.opts.standalone_builder:
            # We simply expect that 'copr-builder' package is installed on the
            # builder machine.
            return

        # do check of host
        try:
            # requires name resolve facility
            socket.gethostbyname(self.hostname)
        except IOError:
            raise BuilderError("{0} could not be resolved".format(self.hostname))

        try:
            self._run_ssh_cmd("/bin/rpm -q mock rsync")
        except RemoteCmdError:
            raise BuilderError(msg="Build host `{0}` does not have mock or rsync installed"
                               .format(self.hostname))

        # test for path existence for mockchain and chroot config for this chroot
        try:
            self._run_ssh_cmd("/usr/bin/test -f {0}".format(mockchain))
        except RemoteCmdError:
            raise BuilderError(msg="Build host `{}` missing mockchain binary `{}`"
                               .format(self.hostname, mockchain))

        try:
            self._run_ssh_cmd("/usr/bin/test -f /etc/mock/{}.cfg"
                              .format(self.job.chroot))
        except RemoteCmdError:
            raise BuilderError(msg="Build host `{}` missing mock config for chroot `{}`"
                               .format(self.hostname, self.job.chroot))
