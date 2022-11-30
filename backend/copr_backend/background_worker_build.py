"""
BuildBackgroundWorker class + internals.
"""

import glob
import logging
import os
import shlex
import shutil
import statistics
import time
import json

from packaging import version

from copr_common.enums import StatusEnum

from copr_backend.background_worker import BackendBackgroundWorker
from copr_backend.cancellable_thread import CancellableThreadTask
from copr_backend.constants import build_log_format
from copr_backend.exceptions import CoprSignError, CoprBackendError
from copr_backend.helpers import (
    call_copr_repo, pkg_name_evr, run_cmd, register_build_result,
)
from copr_backend.job import BuildJob
from copr_backend.msgbus import MessageSender
from copr_backend.sign import sign_rpms_in_dir, get_pubkey
from copr_backend.sshcmd import SSHConnection, SSHConnectionError
from copr_backend.vm_alloc import ResallocHostFactory


MAX_HOST_ATTEMPTS = 3
MAX_SSH_ATTEMPTS = 5
MIN_BUILDER_VERSION = "0.54.1.dev"
CANCEL_CHECK_PERIOD = 5

MESSAGES = {
    "give_up_repo":
        "Giving up waiting for copr_base repository, "
        "please try to manually regenerate the DNF repository "
        "(e.g. by 'copr-cli regenerate-repos <project_name>')",
    "repo_waiting":
        "Waiting for copr_base repository",
    "copr_rpmbuild_missing":
        "The copr-rpmbuild package was not found: {}",
}

COMMANDS = {
    "rpm_q_builder": "rpm -q copr-rpmbuild --qf \"%{VERSION}\n\"",
}


class BuildRetry(Exception):
    """
    Stop processing the build on the current host, and ask for a new
    one (even though the same may be given by the Resalloc server).
    So we re-try the build as long as the host seems to reply on SSH
    channel and it makes at least some sense.  We also retry on at most
    MAX_HOST_ATTEMPTS hosts when the hosts suddenly become unusable.
    """

class BuildCanceled(Exception):
    """ Synchronous cancel request received, fail the build! """
    def __str__(self):
        return "Build was canceled"

class BackendError(Exception):
    """ Generic build failure. """
    def __str__(self):
        return "Backend process error: {}".format(super().__str__())


def _average_step(values):
    """
    Calculate average step between ``values``.  It's expected that
    ``values`` contains at least two items.
    """
    if len(values) < 4:
        return float("inf")
    previous = None
    intervals = []
    for value in values:
        if previous:
            intervals.append(value - previous)
        previous = value
    return statistics.mean(intervals)


class LoggingPrivateFilter(logging.Filter):
    """
    Filter-out messages that can potentially reveal some data that
    should stay private.
    """
    def filter(self, record):
        if record.exc_info:
            traceback = record.exc_info[2]
            while traceback.tb_next:
                traceback = traceback.tb_next
            fname = traceback.tb_frame.f_code.co_filename
            fline = traceback.tb_frame.f_lineno

            record.exc_info = None
            record.exc_text = ""
            record.msg = record.msg + " (in {}:{})".format(
                fname, fline,
            )

        return 1

class BuildBackgroundWorker(BackendBackgroundWorker):
    """
    The (S)RPM build logic.
    """
    # pylint: disable=too-many-instance-attributes

    redis_logger_id = 'worker'

    def __init__(self):
        super().__init__()
        self.sender = None
        self.builder_pid = None
        self.builder_dir = "/var/lib/copr-rpmbuild"
        self.builder_livelog = os.path.join(self.builder_dir, "main.log")
        self.builder_results = os.path.join(self.builder_dir, "results")
        self.ssh = None
        self.job = None
        self.host = None
        self.canceled = False
        self.last_hostname = None

    @classmethod
    def adjust_arg_parser(cls, parser):
        parser.add_argument(
            "--build-id",
            type=int,
            required=True,
            help="build ID to process",
        )
        parser.add_argument(
            "--chroot",
            required=True,
            help="chroot name (or 'srpm-builds')",
        )

    @property
    def name(self):
        """ just a name for logging purposes """
        return "backend.worker-{}".format(self.worker_id)

    def _prepare_result_directory(self, job):
        """
        Create backup directory and move there results from previous build.
        """
        try:
            os.makedirs(job.results_dir)
        except FileExistsError:
            pass

        if not os.listdir(job.results_dir):
            return

        backup_dir_name = "prev_build_backup"
        backup_dir = os.path.join(job.results_dir, backup_dir_name)
        self.log.info("Cleaning target directory, results from previous build storing in %s",
                      backup_dir)

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        files = (x for x in os.listdir(job.results_dir) if x != backup_dir_name)
        for filename in files:
            file_path = os.path.join(job.results_dir, filename)
            if os.path.isfile(file_path):
                if file_path.endswith((".info", ".log", ".log.gz")):
                    os.rename(file_path, os.path.join(backup_dir, filename))

                elif not file_path.endswith(".rpm"):
                    os.remove(file_path)
            else:
                shutil.rmtree(file_path)

    def _setup_resultdir_and_logging(self):
        """ Prepare the result directory and log file ASAP """
        self._prepare_result_directory(self.job)
        handler = logging.FileHandler(
            filename=self.job.backend_log,
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(build_log_format)
        handler.addFilter(LoggingPrivateFilter())
        self.log.addHandler(handler)

    def _mark_starting(self):
        """
        Announce to the frontend that the build is starting. Frontend may reject
        build to start.
        """
        self.log.info("Marking build as starting")
        self.job.status = StatusEnum("starting")
        if not self.frontend_client.starting_build(self.job.to_dict()):
            raise BackendError("Frontend forbade to start the job {}".format(
                self.job.task_id))

    def _check_copr_builder(self):
        rc, out, err = self.ssh.run_expensive(COMMANDS["rpm_q_builder"])
        if rc != 0:
            raise BuildRetry(MESSAGES["copr_rpmbuild_missing"].format(err))
        if version.parse(out) < version.parse(MIN_BUILDER_VERSION):
            # retry for this issue indefinitely, till the VM is removed and
            # up2date is spawned
            raise BuildRetry("Minimum version for builder is {}"
                             .format(MIN_BUILDER_VERSION))

    def _check_mock_config(self):
        config = "/etc/mock/{}.cfg".format(self.job.chroot)
        command = "/usr/bin/test -f " + config
        if self.job.chroot == "srpm-builds":
            return
        if self.ssh.run(command):
            raise BuildRetry("Chroot config {} not found".format(config))

    def _check_vm(self):
        """
        Check that the VM is OK to start the build
        """
        self.log.info("Checking that builder machine is OK")
        self._check_copr_builder()
        self._check_mock_config()

    def _fill_build_info_file(self):
        """
        Places "build.info" which contains job build_id and worker IP
        into the directory with downloaded files.
        """
        info_file_path = os.path.join(self.job.results_dir, "build.info")
        self.log.info("Filling build.info file with builder info")
        try:
            with open(info_file_path, 'w') as info_file:
                info_file.writelines([
                    "build_id={}".format(self.job.build_id),
                    "\nbuilder_ip={}".format(self.host.hostname)])

        except Exception as error:
            raise BackendError("Can't write to {}: {}".format(
                info_file_path, error,
            ))

    def _mark_running(self, attempt):
        """
        Announce everywhere that a build process started now.
        """
        self._proctitle("Job {}, host info: {}".format(self.job.task_id,
                                                       self.host.info))
        self.job.started_on = time.time()
        self.job.status = StatusEnum("running")

        if attempt > 0:
            # TODO: invent new message type for re-try
            self.log.info("Not re-notifying FE and msg buses for the new host.")
            return

        self.log.info("Marking build as running on frontend")
        data = {"builds": [self.job.to_dict()]}
        self.frontend_client.update(data)

        for topic in ['build.start', 'chroot.start']:
            self.sender.announce(topic, self.job, self.last_hostname)

    def _mark_finished(self):
        self.job.ended_on = time.time()

        # At this point, NEVER want to re-try the build by subsequent
        # BackgroundWorker process.  Let's enforce "finished" state.
        allowed_states = "failed", "succeeded"
        if self.job.status not in [StatusEnum(s) for s in allowed_states]:
            self.log.warning("Switching not-finished job state to 'failed'")
            self.job.status = StatusEnum("failed")

        text_status = StatusEnum(self.job.status)
        self.log.info("Worker %s build, took %s", text_status,
                      self.job.took_seconds)
        data = {"builds": [self.job.to_dict()]}
        self.frontend_client.update(data)
        self.sender.announce("build.end", self.job, self.last_hostname)

    def _parse_results(self):
        """
        Parse `results.json` and update the `self.job` object.
        """
        if self.job.chroot == "srpm-builds":
            # We care only about final RPMs
            return

        path = os.path.join(self.job.results_dir, "results.json")
        if not os.path.exists(path):
            raise BackendError("results.json file not found in resultdir")
        with open(path, "r") as f:
            results = json.load(f)
        self.job.results = results

    def _wait_for_repo(self):
        """
        Wait a while for initial createrepo, and eventually fail the build
        if the waiting is not successful.
        """
        if self.job.chroot == 'srpm-builds':
            # we don't need copr_base repodata for srpm builds
            return

        repodata = os.path.join(self.job.chroot_dir, "repodata/repomd.xml")
        waiting_since = time.time()
        while time.time() - waiting_since < 60:
            if os.path.exists(repodata):
                return

            # Either (a) the very first copr-repo run in this chroot dir
            # is still running on background (or failed), or (b) we are
            # hitting the race condition between
            # 'rm -rf repodata && mv .repodata repodata' sequence that
            # is done in createrepo_c.  Try again after some time.
            self.log.info(MESSAGES["repo_waiting"])
            time.sleep(2)

        # This should never happen, but if yes - we need to debug
        # properly.  Give up waiting, and fail the build.  That should
        # motivate people to report bugs.
        raise BackendError(MESSAGES["give_up_repo"])

    def _get_build_job(self):
        """
        Per self.args, obtain BuildJob instance.
        """
        if self.args.chroot == "srpm-builds":
            target = "get-srpm-build-task/{}".format(self.args.build_id)
        else:
            target = "get-build-task/{}-{}".format(self.args.build_id,
                                                   self.args.chroot)
        resp = self.frontend_client.get(target)
        if resp.status_code != 200:
            self.log.error("Failed to download build info, apache code %s",
                           resp.status_code)
            raise BackendError("Failed to get the build task {}".format(target))

        self.job = BuildJob(resp.json(), self.opts)
        self.job.started_on = time.time()
        if not self.job.chroot:
            raise BackendError("Frontend job doesn't provide chroot")

    def _drop_host(self):
        """
        Deallocate assigned host.  We can call this multiple times in row (to
        make sure the host is deallocated), so this needs to stay idempotent.
        """
        if not self.host:
            return

        self.log.info("Releasing VM back to pool")
        self.host.release()
        self.host = None

    def _proctitle(self, text):
        text = "Builder for task {}: {}".format(self.job.task_id, text)
        self.log.debug("setting title: %s", text)
        self.setproctitle(text)

    def _cancel_task_check_request(self):
        self.canceled = bool(self.redis_get_worker_flag("cancel_request"))
        return self.canceled

    def _cancel_if_requested(self):
        """
        Raise BuildCanceled exception if there's already a request for
        cancellation.  This is useful as "quick and cheap check" before starting
        some expensive task that would have to be later canceled anyways.
        We can call this multiple times, anytime we feel it is appropriate.
        """
        if self._cancel_task_check_request():
            self.log.warning("Canceling the build early")
            self._drop_host()
            raise BuildCanceled

    def _cancel_vm_allocation(self):
        self.redis_set_worker_flag("canceling", 1)
        self._drop_host()

    def _alloc_host(self):
        """
        Set self.host with ready RemoteHost, and return True.  Keep re-trying
        upon allocation failure.  Return False if the request was canceled.
        """
        self.log.info("Trying to allocate VM")

        vm_factory = ResallocHostFactory(server=self.opts.resalloc_connection)
        while True:
            self.host = vm_factory.get_host(self.job.tags, self.job.sandbox)
            self._proctitle("Waiting for VM, info: {}".format(self.host.info))
            success = CancellableThreadTask(
                self.host.wait_ready,
                self._cancel_task_check_request,
                self._cancel_vm_allocation,
                check_period=CANCEL_CHECK_PERIOD,
            ).run()
            if self.canceled:
                raise BuildCanceled
            if success:
                self.log.info("Allocated host %s", self.host.info)
                self.last_hostname = self.host.hostname
                return
            time.sleep(60)
            self.log.error("VM allocation failed, trying to allocate new VM")

    def _alloc_ssh_connection(self):
        self.log.info("Allocating ssh connection to builder")
        self.ssh = SSHConnection(
            user=self.opts.build_user,
            host=self.host.hostname,
            config_file=self.opts.ssh.builder_config
        )

    def _cancel_running_worker(self):
        """
        This is "canceling" callback to CancellableThreadTask, so please never
        raise any exception.  The worst case scenario is that nothing is
        canceled.
        """
        self._proctitle("Canceling running task...")
        self.redis_set_worker_flag("canceling", 1)
        try:
            cmd = "copr-rpmbuild-cancel"
            rc, out, err = self.ssh.run_expensive(cmd, max_retries=3)
            if rc:
                self.log.warning("Can't cancel build\nout:\n%s\nerr:\n%s",
                                 out, err)
                return
            self.log.info("Cancel request succeeded\nout:\n%serr:\n%s",
                          out, err)
        except SSHConnectionError:
            self.log.error("Can't ssh to cancel build.")

    def _start_remote_build(self):
        """ start the RPM build on builder on background """
        command = "copr-rpmbuild --verbose --drop-resultdir"
        if self.job.chroot == "srpm-builds":
            command += " --srpm --build-id {build_id} --detached"
        else:
            command += " --build-id {build_id} --chroot {chroot} --detached"
        command = command.format(build_id=self.job.build_id,
                                 chroot=self.job.chroot)

        self.log.info("Starting remote build: %s", command)
        rc, stdout, stderr = self.ssh.run_expensive(command)
        if rc:
            raise BackendError("Can't start copr-rpmbuild,\nout:\n{}err:\n{}"
                               .format(stdout, stderr))
        try:
            self.builder_pid = int(stdout.strip())
        except ValueError:
            raise BackendError("copr-rpmbuild returned invalid PID "
                               "on stdout: {}".format(stdout))

    def _tail_log_file(self):
        """ Return None if OK, or failure reason as str """
        live_cmd = "copr-rpmbuild-log"
        with open(self.job.builder_log, 'w') as logfile:
            # We can not use 'max_retries' here because that would concatenate
            # the attempts to the same log file.
            if self.ssh.run(live_cmd, stdout=logfile, stderr=logfile):
                return "{} shouldn't exit != 0".format(live_cmd)
        return None

    def _retry_for_ssh_failures(self, method, *args, **kwargs):
        """
        Retry running the ``method`` indefinitely when SSHConnectionError occurs
        more frequently than each 2 minutes.
        """
        attempt = 0
        ssh_failures = []
        while True:
            attempt += 1
            try:
                self.log.info("Downloading the builder-live.log file, "
                              "attempt %s", attempt)
                return method(*args, **kwargs)
            except SSHConnectionError as exc:
                ssh_failures += [time.time()]
                if _average_step(ssh_failures[-4:]) < 120:
                    self.log.error("Giving up for unstable SSH, failures: %s",
                                   ", ".join([str(x) for x in ssh_failures]))
                    raise
                sleep = 10
                self.log.warning("SSH connection lost on #%s attempt, "
                                 "let's retry after %ss, %s", attempt, sleep, exc)
                time.sleep(sleep)
                continue

    def _transfer_log_file(self):
        """
        Since the tail process can be "watched" for a very long time, there's
        quite some chance we loose ssh connection in the meantime.  Therefore
        re-try downloading it till the ssh "looks" to be working.

        This is "cancellable" task, so we should NEVER RAISE any exception.
        """
        try:
            return self._retry_for_ssh_failures(self._tail_log_file)
        except SSHConnectionError as exc:
            return "Stopped following builder for broken SSH: {}".format(exc)

    def _compress_live_logs(self):
        """
        Compress builder-live.log and backend.log by gzip.
        Never raise any exception!
        """
        logs = [
            self.job.builder_log,
            self.job.backend_log,
        ]

        # For automatic redirect from log to log.gz, consider configuring
        # Lighttpd like:
        #
        #   url.redirect += ( "^/(.*)/redirect-builder-live.log$" => "/$1/builder-live.log.gz" )
        #   url.rewrite-if-not-file = ("^/(.*)/builder-live.log$" => "/$1/redirect-builder-live.log")
        #   url.redirect += ( "^/(.*)/redirect-backend.log$" => "/$1/backend.log.gz" )
        #   url.rewrite-if-not-file += ("^/(.*)/backend.log$" => "/$1/redirect-backend.log")
        #
        #   $HTTP["url"] =~ "\.log\.gz$" {
        #       magnet.attract-physical-path-to = ( "/etc/lighttpd/content-encoding-gzip-if-exists.lua" )
        #       mimetype.assign = ("" => "text/plain" )
        #   }
        #
        # .. here the Lua script looks just like:
        #
        #   if (lighty.stat(lighty.env["physical.path"])) then
        #     lighty.header["Content-Encoding"] = "gzip"
        #   end
        #
        # Or Apache with:
        #     <FilesMatch "^(builder-live|backend)\.log$">
        #     RewriteEngine on
        #     RewriteCond %{REQUEST_FILENAME} !-f
        #     RewriteRule ^(.*)$ %{REQUEST_URI}.gz [R]
        #     </FilesMatch>

        for src in logs:
            dest = src + ".gz"
            if os.path.exists(dest):
                # This shouldn't ever happen, but if it happened - gzip below
                # would interactively ask whether we want to overwrite the
                # existing file, and it would deadlock the worker.
                self.log.error("Compressed log %s exists", dest)
                continue

            self.log.info("Compressing %s by gzip", src)
            res = run_cmd(["gzip", src], logger=self.log)
            if res.returncode not in [0, 2]:
                self.log.error("Unable to compress file %s", src)

    def _download_results(self):
        """
        Retry rsync-download the results several times.
        """
        self.log.info("Downloading results from builder")
        self.ssh.rsync_download(
            self.builder_results + "/",
            self.job.results_dir,
            logfile=self.job.rsync_log_name,
            max_retries=2,
        )

    def _check_build_success(self):
        """
        Raise BackendError if builder claims that the build failed.
        """
        self.log.info("Searching for 'success' file in resultdir")
        successfile = os.path.join(self.job.results_dir, "success")
        if not os.path.exists(successfile):
            raise BackendError("No success file => build failure")

    def _sign_built_packages(self):
        """
            Sign built rpms
             using `copr_username` and `copr_projectname` from self.job
             by means of obs-sign. If user builds doesn't have a key pair
             at sign service, it would be created through ``copr-keygen``

        :param chroot_dir: Directory with rpms to be signed
        :param pkg: path to the source package

        """

        self.log.info("Going to sign pkgs from source: %s in chroot: %s",
                      self.job.task_id, self.job.chroot_dir)

        sign_rpms_in_dir(
            self.job.project_owner,
            self.job.project_name,
            os.path.join(self.job.chroot_dir, self.job.target_dir_name),
            self.job.chroot,
            opts=self.opts,
            log=self.log
        )

        self.log.info("Sign done")

    def _do_createrepo(self):
        if self.job.chroot == 'srpm-builds':
            return

        project_owner = self.job.project_owner
        project_name = self.job.project_name
        devel = self.job.uses_devel_repo
        appstream = self.job.appstream

        base_url = "/".join([self.opts.results_baseurl, project_owner,
                             project_name, self.job.chroot])

        self.log.info("Incremental createrepo run, adding %s into %s, "
                      "(auto-create-repo=%s)", self.job.target_dir_name,
                      base_url, not devel)
        if not call_copr_repo(self.job.chroot_dir, devel=devel,
                              add=[self.job.target_dir_name],
                              logger=self.log,
                              appstream=appstream):
            raise BackendError("createrepo failed")

    def _get_srpm_build_details(self, job):
        build_details = {'srpm_url': ''}
        self.log.info("Retrieving srpm URL from %s", job.results_dir)
        pattern = os.path.join(job.results_dir, '*.src.rpm')
        srpm_file = glob.glob(pattern)[0]
        srpm_name = os.path.basename(srpm_file)
        srpm_url = os.path.join(job.results_dir_url, srpm_name)
        build_details['pkg_name'], build_details['pkg_version'] = \
                pkg_name_evr(srpm_file, self.log)
        build_details['srpm_url'] = srpm_url
        self.log.info("SRPM URL: %s", srpm_url)
        return build_details

    def _collect_built_packages(self, job):
        self.log.info("Listing built binary packages in %s",
                      job.results_dir)

        cmd = (
            "builtin cd {0} && "
            "for f in `ls *.rpm | grep -v \"src.rpm$\"`; do"
            "   rpm --nosignature -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(shlex.quote(job.results_dir))
        )

        result = run_cmd(cmd, shell=True, logger=self.log)
        built_packages = result.stdout.strip()
        self.log.info("Built packages:\n%s", built_packages)
        return built_packages


    def _get_build_details(self, job):
        """
        :return: dict with build_details
        :raises BackendError: Something happened with build itself
        """
        self.log.info("Getting build details")
        try:
            if job.chroot == "srpm-builds":
                build_details = self._get_srpm_build_details(job)
            else:
                build_details = {
                    "built_packages": self._collect_built_packages(job),
                }
            self.log.info("build details: %s", build_details)
        except Exception as e:
            raise BackendError(
                "Error while collecting built packages for {}: {}"
                .format(job.task_id, str(e)))

        return build_details

    def _add_pubkey(self):
        """
        Adds pubkey.gpg with public key to ``chroot_dir`` using
        ``copr_username`` and ``copr_projectname`` from self.job.
        """
        if not self.opts.do_sign:
            return

        self.log.info("Retrieving pubkey")

        # TODO: sign repodata as well ?
        user = self.job.project_owner
        project = self.job.project_name
        pubkey_path = os.path.join(self.job.destdir, "pubkey.gpg")

        # TODO: uncomment this when key revoke/change will be implemented
        # if os.path.exists(pubkey_path):
        #    return
        get_pubkey(user, project, self.log, pubkey_path)
        self.log.info("Added pubkey for user %s project %s into: %s",
                      user, project, pubkey_path)

    def build(self, attempt):
        """
        Attempt to build.
        """
        failed = True

        self._wait_for_repo()
        self._cancel_if_requested()
        self._alloc_host()
        self._alloc_ssh_connection()
        self._check_vm()
        self._fill_build_info_file()
        self._cancel_if_requested()
        self._mark_running(attempt)
        self._start_remote_build()
        transfer_failure = CancellableThreadTask(
            self._transfer_log_file,
            self._cancel_task_check_request,
            self._cancel_running_worker,
            check_period=CANCEL_CHECK_PERIOD,
        ).run()
        if self.canceled:
            raise BuildCanceled
        if transfer_failure:
            raise BuildRetry("SSH problems when downloading live log: {}"
                             .format(transfer_failure))
        self._download_results()
        self._drop_host()

        # raise error if build failed
        try:
            self._check_build_success()
            # Build _succeeded_.  Do the tasks for successful run.
            failed = False
            if self.opts.do_sign:
                self._sign_built_packages()
            self._do_createrepo()
            self._parse_results()
            build_details = self._get_build_details(self.job)
            self.job.update(build_details)
            self.job.validate()
            self._add_pubkey()
        except:
            failed = True
            raise
        finally:
            self.log.info("Finished build: id=%s failed=%s timeout=%s "
                          "destdir=%s chroot=%s ", self.job.build_id,
                          failed, self.job.timeout, self.job.destdir,
                          self.job.chroot)
            self.job.status = StatusEnum("failed" if failed else "succeeded")
            register_build_result(self.opts, failed)

    def retry_the_build(self):
        """
        Indefinitely (at most on MAX_HOST_ATTEMPTS hosts though) retry
        the build if BuildRetry is raised.
        """
        attempt = 0
        seen_hosts = set()
        while True:
            try:
                return self.build(attempt)
            except (BuildRetry, SSHConnectionError) as exc:
                seen_hosts.add(self.host.hostname)
                attempt += 1
                self.log.error("Re-try request for task on '%s': %s",
                               self.host.info, str(exc))
                self._drop_host()
                if len(seen_hosts) >= MAX_HOST_ATTEMPTS:
                    raise BackendError("Three host tried without success: {}"
                                       .format(seen_hosts))
                self.log.info("Retry #%s (on other host)", attempt)
                continue

    def handle_build(self):
        """ Do the build """
        self.sender = MessageSender(self.opts, self.name, self.log)
        self._get_build_job()
        self._setup_resultdir_and_logging()
        self._mark_starting()
        return self.retry_the_build()

    def handle_task(self):
        """ called by WorkerManager (entry point) """
        try:
            self.handle_build()
        except (BackendError, BuildCanceled, CoprBackendError) as err:
            self.log.error(str(err))
        except CoprSignError as err:
            self.log.error("Copr GPG signing problems: %s", str(err))
        except Exception:  # pylint: disable=broad-except
            self.log.exception("Unexpected exception")
        finally:
            self._drop_host()
            if self.job:
                self._mark_finished()
                self._compress_live_logs()
            else:
                self.log.error("No job object from Frontend")
            self.redis_set_worker_flag("status", "done")
