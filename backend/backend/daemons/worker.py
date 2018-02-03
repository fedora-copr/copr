from datetime import datetime
import json
import os
import time
import gzip
import shutil
import multiprocessing
import pipes
import glob
from setproctitle import setproctitle

from ..exceptions import MockRemoteError, CoprWorkerError, VmError, NoVmAvailable
from ..job import BuildJob
from ..mockremote import MockRemote
from ..constants import BuildStatus, build_log_format
from ..helpers import register_build_result, get_redis_connection, get_redis_logger, \
    local_file_logger, run_cmd
from ..vm_manage import VmStates

from ..msgbus import MsgBusStomp, MsgBusFedmsg
from ..sshcmd import SSHConnectionError


# ansible_playbook = "ansible-playbook"

class Worker(multiprocessing.Process):
    msg_buses = []

    def __init__(self, opts, frontend_client, vm_manager, worker_id, vm, job, reattach=False):
        multiprocessing.Process.__init__(self, name="worker-{}".format(worker_id))

        self.opts = opts
        self.frontend_client = frontend_client
        self.vm_manager = vm_manager
        self.worker_id = worker_id
        self.vm = vm
        self.job = job
        self.reattach = reattach

        self.log = get_redis_logger(self.opts, self.name, "worker")

    @property
    def name(self):
        return "backend.worker-{}-{}".format(self.worker_id, self.group_name)

    @property
    def group_name(self):
        try:
            return self.opts.build_groups[self.vm.group]["name"]
        except Exception as error:
            self.log.exception("Failed to get builder group name from config, using group_id as name."
                               "Original error: {}".format(error))
            return str(self.vm.group)


    def _announce(self, topic, job):
        for bus in self.msg_buses:
            bus.announce_job(
                topic, job,
                who=self.name,
                ip=self.vm.vm_ip,
                pid=self.pid
            )


    def _announce_start(self, job):
        """
        Announce everywhere that a build process started now.
        """
        self.mark_started(job)

        for topic in ['build.start', 'chroot.start']:
            self._announce(topic, job)


    def _announce_end(self, job):
        """
        Announce everywhere that a build process ended now.
        """
        job.ended_on = time.time()
        self.return_results(job)
        self.log.info("worker finished build: {0}".format(self.vm.vm_ip))
        self._announce('build.end', job)

    def mark_started(self, job):
        """
        Send data about started build to the frontend
        """
        job.started_on = time.time()

        job.status = BuildStatus.RUNNING
        build = job.to_dict()
        self.log.info("starting build: {}".format(build))

        data = {"builds": [build]}
        try:
            self.frontend_client.update(data)
        except:
            raise CoprWorkerError("Could not communicate to front end to submit status info")

    def return_results(self, job):
        """
        Send the build results to the frontend
        """
        self.log.info("Build {} finished with status {}. Took {} seconds"
                      .format(job.build_id, job.status, job.ended_on - job.started_on))

        data = {"builds": [job.to_dict()]}

        try:
            self.frontend_client.update(data)
        except Exception as err:
            raise CoprWorkerError(
                "Could not communicate to front end to submit results: {}"
                .format(err)
            )

    @classmethod
    def pkg_built_before(cls, pkg, chroot, destdir):
        """
        Check whether the package has already been built in this chroot.
        """
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace(".src.rpm", "")
        resdir = "{0}/{1}/{2}".format(destdir, chroot, pdn)
        resdir = os.path.normpath(resdir)
        if os.path.exists(resdir) and os.path.exists(os.path.join(resdir, "success")):
            return True
        return False

    def init_buses(self):
        self.log.info(self.opts.msg_buses)
        for bus_config in self.opts.msg_buses:
            self.msg_buses.append(MsgBusStomp(bus_config, self.log))

        if self.opts.fedmsg_enabled:
            self.msg_buses.append(MsgBusFedmsg(self.log))

    # TODO: doing skip logic on fronted during @start_build query
    # def on_pkg_skip(self, job):
    #     """
    #     Handle package skip
    #     """
    #     self._announce_start(job)
    #     self.log.info("Skipping: package {} has been already built before.".format(job.pkg))
    #     job.status = BuildStatus.SKIPPED
    #     self._announce_end(job)

    def do_job(self, job):
        """
        Executes new job.

        :param job: :py:class:`~backend.job.BuildJob`
        """
        failed = False
        self.update_process_title(suffix="Task: {} chroot: {} build running"
                                  .format(job.build_id, job.chroot))

        if not self.reattach:
            self._announce_start(job)
        else:
            self.mark_started(job)

        # setup our target dir locally
        if not os.path.exists(job.chroot_dir):
            try:
                os.makedirs(job.chroot_dir)
            except (OSError, IOError):
                self.log.exception("Could not make results dir for job: {}"
                                   .format(job.chroot_dir))
                failed = True

        if not self.reattach:
            self.clean_result_directory(job)

        if not failed:
            # FIXME
            # need a plugin hook or some mechanism to check random
            # info about the pkgs
            # this should use ansible to download the pkg on
            # the remote system
            # and run a series of checks on the package before we
            # start the build - most importantly license checks.

            self.log.info("Starting build: id={} builder={} job: {}"
                          .format(job.build_id, self.vm.vm_ip, job))

            with local_file_logger(
                "{}.builder.mr".format(self.name),
                job.chroot_log_path,
                fmt=build_log_format) as build_logger:

                try:
                    mr = MockRemote(
                        builder_host=self.vm.vm_ip,
                        job=job,
                        logger=build_logger,
                        opts=self.opts
                    )

                    if self.reattach:
                        mr.reattach_to_pkg_build()
                    else:
                        mr.check()
                        mr.build_pkg()

                    mr.check_build_success() # raises if build didn't succeed
                    mr.download_results()

                except MockRemoteError as e:
                    # record and break
                    self.log.exception(
                        "Error during the build, host={}, build_id={}, chroot={}"
                        .format(self.vm.vm_ip, job.build_id, job.chroot)
                    )
                    failed = True
                    mr.download_results()

                except SSHConnectionError as err:
                    self.log.exception(
                        "SSH connection stalled: {0}".format(str(err)))
                    # The VM is unusable, don't wait for relatively slow
                    # garbage collector.
                    self.vm_manager.start_vm_termination(self.vm.vm_name)
                    self.frontend_client.reschedule_build(
                            job.build_id, job.chroot)
                    raise VmError("SSH connection issue, build rescheduled")

                except: # programmer's failure
                    self.log.exception("Unexpected error")
                    failed = True

                if not failed:
                    try:
                        mr.on_success_build()
                        build_details = self.get_build_details(job)
                        job.update(build_details)

                        if self.opts.do_sign:
                            mr.add_pubkey()
                    except:
                        self.log.exception("Error during backend post-build processing.")
                        failed = True

            self.log.info(
                "Finished build: id={} builder={} timeout={} destdir={} chroot={}"
                .format(job.build_id, self.vm.vm_ip, job.timeout, job.destdir,
                        job.chroot))
            self.copy_logs(job)

        register_build_result(self.opts, failed=failed)
        job.status = (BuildStatus.FAILURE if failed else BuildStatus.SUCCEEDED)

        self._announce_end(job)
        self.update_process_title(suffix="Task: {} chroot: {} done"
                                  .format(job.build_id, job.chroot))

    def collect_built_packages(self, job):
        self.log.info("Listing built binary packages in {}"
                      .format(job.results_dir))

        cmd = (
            "builtin cd {0} && "
            "for f in `ls *.rpm | grep -v \"src.rpm$\"`; do"
            "   rpm -qp --qf \"%{{NAME}} %{{VERSION}}\n\" $f; "
            "done".format(pipes.quote(job.results_dir))
        )
        result = run_cmd(cmd, shell=True)
        built_packages = result.stdout.strip()
        self.log.info("Built packages:\n{}".format(built_packages))
        return built_packages

    def get_srpm_url(self, job):
        self.log.info("Retrieving srpm URL for {}".format(job.results_dir))
        try:
            pattern = os.path.join(job.results_dir, '*.src.rpm')
            srpm_name = os.path.basename(glob.glob(pattern)[0])
            srpm_url = os.path.join(job.results_dir_url, srpm_name)
        except IndexError:
            srpm_url = ""

        self.log.info("SRPM URL: {}".format(srpm_url))
        return srpm_url

    def get_build_details(self, job):
        """
        :return: dict with build_details
        :raises MockRemoteError: Something happened with build itself
        """
        try:
            if job.chroot == "srpm-builds":
                build_details = { "srpm_url": self.get_srpm_url(job) }
            else:
                build_details = { "built_packages": self.collect_built_packages(job) }
            self.log.info("build details: {}".format(build_details))
        except Exception as e:
            self.log.exception(str(e))
            raise CoprWorkerError("Error while collecting built packages for {}.".format(job))

        return build_details

    def copy_logs(self, job):
        if not os.path.isdir(job.results_dir):
            self.log.info("Job results dir doesn't exists, couldn't copy main log; path: {}"
                          .format(job.results_dir))
            return

        logs_to_copy = [
            (os.path.join(job.chroot_log_path),
             os.path.join(job.results_dir, "backend.log.gz"))
        ]

        for src, dst in logs_to_copy:
            try:
                with open(src, "rb") as f_src, gzip.open(dst, "wb") as f_dst:
                    f_dst.writelines(f_src)
            except IOError:
                self.log.info("File {} not found".format(src))

    def clean_result_directory(self, job):
        """
        Create backup directory and move there results from previous build.
        """
        if not os.path.exists(job.results_dir) or os.listdir(job.results_dir) == []:
            return

        backup_dir_name = "prev_build_backup"
        backup_dir = os.path.join(job.results_dir, backup_dir_name)
        self.log.info("Cleaning target directory, results from previous build storing in {}"
                      .format(backup_dir))

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

    def update_process_title(self, suffix=None):
        title = "Worker-{}-{} ".format(self.worker_id, self.group_name)
        title += "vm.vm_ip={} ".format(self.vm.vm_ip)
        title += "vm.vm_name={} ".format(self.vm.vm_name)
        if suffix:
            title += str(suffix)
        setproctitle(title)

    def run(self):
        self.log.info("Starting worker")
        self.init_buses()

        try:
            self.do_job(self.job)
        except VmError as error:
            self.log.exception("Building error: {}".format(error))
        except Exception as e:
            self.log.exception("Unexpected error: {}".format(e))
        finally:
            self.vm_manager.release_vm(self.vm.vm_name)
