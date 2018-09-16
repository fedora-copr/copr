import os
import pipes
from subprocess import Popen

from backend.vm_manage import PUBSUB_INTERRUPT_BUILDER

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd

from ..helpers import get_redis_connection, ensure_dir_exists
from ..exceptions import BuilderError, RemoteCmdError, VmError
from ..constants import rsync
from ..sshcmd import SSHConnection



class Builder(object):

    def __init__(self, opts, hostname, job, logger):

        self.opts = opts
        self.hostname = hostname
        self.job = job
        self.timeout = self.job.timeout or self.opts.timeout
        self.log = logger

        # BACKEND/BUILDER API

        if self.opts.builder_deprecated:
            self.builddir = "/var/lib/copr-builder"
            self.livelog_name = os.path.join(self.builddir, 'live-log')
        else:
            self.builddir = "/var/lib/copr-rpmbuild"
            self.livelog_name = os.path.join(self.builddir, 'main.log')

        self.resultdir = os.path.join(self.builddir, 'results')
        self.pidfile = os.path.join(self.builddir, 'pid')

        self.conn = SSHConnection(
            user=self.opts.build_user,
            host=self.hostname,
            config_file=self.opts.ssh.builder_config
        )

        self.module_dist_tag = self._load_module_dist_tag()
        self._build_pid = None

    def _load_module_dist_tag(self):
        module_md_filepath = os.path.join(self.job.destdir, self.job.chroot, "module_md.yaml")
        try:
            mmd = Modulemd.ModuleStream()
            mmd.import_from_file(module_md_filepath)
            dist_tag = ".{}+{}+{}".format(mmd.get_name(), (mmd.get_stream() or ''), (str(mmd.get_version()) or '1'))
        except IOError as e:
            return None
        except Exception as e:
            self.log.exception(str(e))
            return None
        else:
            self.log.info("Loaded {}, dist_tag {}".format(module_md_filepath, dist_tag))
        return dist_tag

    def _run_ssh_cmd(self, cmd):
        """
        Executes single shell command remotely

        :param str cmd: shell command
        :return: stdout, stderr as strings
        """
        self.log.info("BUILDER CMD: "+cmd)
        rc, out, err = self.conn.run_expensive(cmd)
        if rc != 0:
            raise RemoteCmdError("Error running remote ssh command.",
                                 cmd, rc, err, out)
        return out, err

    def check_build_success(self):
        successfile = os.path.join(self.resultdir, "success")
        self._run_ssh_cmd("/usr/bin/test -f {0}".format(successfile))

    def run_async_build(self):
        cmd = self._copr_builder_cmd()
        pid, _ = self._run_ssh_cmd(cmd)
        self._build_pid = int(pid.strip())

    def setup_pubsub_handler(self):
        # TODO: is this used?
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

    @property
    def build_pid(self):
        if not self._build_pid:
            try:
                pidof_cmd = "cat {0}".format(self.pidfile)
                out, _ = self._run_ssh_cmd(pidof_cmd)
                self._build_pid = int(out.strip())
            except:
                return None

        return self._build_pid

    def _copr_builder_cmd(self):
        if not self.opts.builder_deprecated:
            return 'copr-rpmbuild --verbose --drop-resultdir '\
                   '--build-id {build_id} --chroot {chroot} --detached'.format(
                       build_id=self.job.build_id, chroot=self.job.chroot)

        template = 'copr-builder --config {config} --copr {copr} ' \
                 + '--package {package} --revision {revision} ' \
                 + '--host-resolv {net} --timeout {timeout} ' \
                 + '--chroot {chroot} --detached '

        if self.module_dist_tag:
            template += '--define {0} '.format(
                pipes.quote('dist ' + self.module_dist_tag))

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
        live_log = os.path.join(self.job.results_dir, 'builder-live.log')

        live_cmd = '/usr/bin/tail -F -n +0 --pid={pid} {log}'.format(
            pid=self.build_pid, log=self.livelog_name)

        self.log.info("Attaching to live build log: " + live_cmd)
        with open(live_log, 'w') as logfile:
            # Ignore the exit status.
            self.conn.run(live_cmd, stdout=logfile, stderr=logfile)

    def build(self):
        # run the build
        self.run_async_build()

        # attach to building output
        self.attach_to_build()

    def reattach(self):
        self.attach_to_build()

    def rsync_call(self, source_path, target_path):
        # TODO: sshcmd.py uses pre-allocated socket, use it here, too
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
            err_msg = ("Failed to download data from builder due to rsync error, "
                       "see the rsync log file for details. Original error: {}".format(error))
            self.log.error(err_msg)
            raise BuilderError(err_msg)

        if cmd.returncode != 0:
            err_msg = "Failed to download data from builder due to rsync error, see the rsync log file for details."
            self.log.error(err_msg)
            raise BuilderError(err_msg)

    def download_results(self, target_path):
        self.rsync_call(self.resultdir, target_path)

    def check(self):
        try:
            self._run_ssh_cmd("/bin/rpm -q copr-rpmbuild")
        except RemoteCmdError:
            raise BuilderError("Build host `{0}` does not have copr-rpmbuild installed"
                               .format(self.hostname))

        # test for path existence for chroot config
        if self.job.chroot != "srpm-builds":
            try:
                self._run_ssh_cmd("/usr/bin/test -f /etc/mock/{}.cfg"
                                  .format(self.job.chroot))
            except RemoteCmdError:
                raise BuilderError("Build host `{}` missing mock config for chroot `{}`"
                                   .format(self.hostname, self.job.chroot))


class SrpmBuilder(Builder):
    def _copr_builder_cmd(self):
        return 'copr-rpmbuild --verbose --drop-resultdir '\
               '--srpm --build-id {build_id} --detached'.format(build_id=self.job.build_id)
