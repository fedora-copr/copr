from datetime import datetime
import json
import logging
import os
import sys
import time
import fcntl
import gzip
import shutil
import multiprocessing
from setproctitle import setproctitle

from retask.queue import Queue

from ..vm_manage.manager import VmManager
from ..exceptions import MockRemoteError, CoprWorkerError, VmError, NoVmAvailable
from ..job import BuildJob
from ..mockremote import MockRemote
from ..constants import BuildStatus, JOB_GRAB_TASK_END_PUBSUB, build_log_format
from ..helpers import register_build_result, format_tb, get_redis_connection, get_redis_logger, create_file_logger


# ansible_playbook = "ansible-playbook"

try:
    import fedmsg
except ImportError:
    # fedmsg is optional
    fedmsg = None


class Worker(multiprocessing.Process):
    """
    Worker process dispatches building tasks. Backend spin-up multiple workers, each
    worker associated to one group_id and process one task at the each moment.

    Worker listens for the new tasks from :py:class:`retask.Queue` associated with its group_id

    :param Munch opts: backend config
    :param int worker_num: worker number
    :param int group_id: group_id from the set of groups defined in config

    """

    def __init__(self, opts, frontend_client, worker_num, group_id):

        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")

        self.opts = opts
        self.worker_num = worker_num
        self.group_id = group_id

        self.log = get_redis_logger(self.opts, self.logger_name, "worker")

        # job management stuff
        self.task_queue = Queue("copr-be-{0}".format(str(group_id)))
        self.task_queue.connect()
        # event queue for communicating back to dispatcher

        self.kill_received = False

        self.frontend_client = frontend_client
        self.vm_name = None
        self.vm_ip = None

        self.rc = None
        self.vmm = VmManager(self.opts)

    @property
    def logger_name(self):
        return "backend.worker-{}-{}".format(self.group_name, self.worker_num)

    @property
    def group_name(self):
        try:
            return self.opts.build_groups[self.group_id]["name"]
        except Exception as error:
            self.log.exception("Failed to get builder group name from config, using group_id as name."
                               "Original error: {}".format(error))
            return str(self.group_id)

    def fedmsg_notify(self, topic, template, content=None):
        """
        Publish message to fedmsg bus when it is available
        :param topic:
        :param template:
        :param content:
        """
        if self.opts.fedmsg_enabled and fedmsg:

            who = "worker-{0}".format(self.worker_num)

            content = content or {}
            content["who"] = who
            content["what"] = template.format(**content)

            try:
                fedmsg.publish(modname="copr", topic=topic, msg=content)
            # pylint: disable=W0703
            except Exception as e:
                self.log.exception("failed to publish message: {0}".format(e))

    def _announce_start(self, job):
        """
        Announce everywhere that a build process started now.
        """
        job.started_on = time.time()
        self.mark_started(job)

        template = "build start: user:{user} copr:{copr}" \
            "pkg: {pkg} build:{build} ip:{ip}  pid:{pid}"

        content = dict(user=job.submitter, copr=job.project_name,
                       owner=job.project_owner, pkg=job.package_name,
                       build=job.build_id, ip=self.vm_ip, pid=self.pid)
        self.fedmsg_notify("build.start", template, content)

        template = "chroot start: chroot:{chroot} user:{user}" \
            "copr:{copr} pkg: {pkg} build:{build} ip:{ip}  pid:{pid}"

        content = dict(chroot=job.chroot, user=job.submitter,
                       owner=job.project_owner, pkg=job.package_name,
                       copr=job.project_name, build=job.build_id,
                       ip=self.vm_ip, pid=self.pid)

        self.fedmsg_notify("chroot.start", template, content)

    def _announce_end(self, job):
        """
        Announce everywhere that a build process ended now.
        """
        job.ended_on = time.time()

        self.return_results(job)
        self.log.info("worker finished build: {0}".format(self.vm_ip))
        template = "build end: user:{user} copr:{copr} build:{build}" \
            "  pkg: {pkg}  version: {version} ip:{ip}  pid:{pid} status:{status}"

        content = dict(user=job.submitter, copr=job.project_name,
                       owner=job.project_owner,
                       pkg=job.package_name, version=job.package_version,
                       build=job.build_id, ip=self.vm_ip, pid=self.pid,
                       status=job.status, chroot=job.chroot)
        self.fedmsg_notify("build.end", template, content)

    def mark_started(self, job):
        """
        Send data about started build to the frontend
        """

        job.status = BuildStatus.RUNNING
        build = job.to_dict()
        self.log.info("starting build: {}".format(build))

        data = {"builds": [build]}
        try:
            self.frontend_client.update(data)
        except:
            raise CoprWorkerError(
                "Could not communicate to front end to submit status info")

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

    def starting_build(self, job):
        """
        Announce to the frontend that a build is starting.
        Checks if we can and/or should start job

        :return True: if the build can start
        :return False: if the build can not start (build is cancelled)
        """

        try:
            return self.frontend_client.starting_build(job.build_id, job.chroot)
        except Exception as err:
            msg = "Could not communicate to front end to confirm build start"
            self.log.exception(msg)
            raise CoprWorkerError(msg)

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

    def init_fedmsg(self):
        """
        Initialize Fedmsg
        (this assumes there are certs and a fedmsg config on disk)
        """

        if not (self.opts.fedmsg_enabled and fedmsg):
            return

        try:
            fedmsg.init(name="relay_inbound", cert_prefix="copr", active=True)
        except Exception as e:
            self.log.exception("Failed to initialize fedmsg: {}".format(e))

    # TODO: doing skip logic on fronted during @start_build query
    # def on_pkg_skip(self, job):
    #     """
    #     Handle package skip
    #     """
    #     self._announce_start(job)
    #     self.log.info("Skipping: package {} has been already built before.".format(job.pkg))
    #     job.status = BuildStatus.SKIPPED
    #     self.notify_job_grab_about_task_end(job)
    #     self._announce_end(job)

    def obtain_job(self):
        """
        Retrieves new build task from queue.
        Checks if the new job can be started and not skipped.
        """
        # ToDo: remove retask, use redis lua fsm logic similiar to VMM
        # this sometimes caused TypeError in random worker
        # when another one  picekd up a task to build
        # why?
        try:
            task = self.task_queue.dequeue()
        except TypeError:
            return
        if not task:
            return

        job = BuildJob(task.data, self.opts)
        self.update_process_title(suffix="Task: {} chroot: {}, obtained at {}"
                                  .format(job.build_id, job.chroot, str(datetime.now())))

        return job

    def do_job(self, job):
        """
        Executes new job.

        :param job: :py:class:`~backend.job.BuildJob`
        """

        self._announce_start(job)
        self.update_process_title(suffix="Task: {} chroot: {} build started"
                                  .format(job.build_id, job.chroot))
        status = BuildStatus.SUCCEEDED

        # setup our target dir locally
        if not os.path.exists(job.chroot_dir):
            try:
                os.makedirs(job.chroot_dir)
            except (OSError, IOError):
                self.log.exception("Could not make results dir for job: {}"
                                   .format(job.chroot_dir))
                status = BuildStatus.FAILURE

        self.clean_result_directory(job)

        if status == BuildStatus.SUCCEEDED:
            # FIXME
            # need a plugin hook or some mechanism to check random
            # info about the pkgs
            # this should use ansible to download the pkg on
            # the remote system
            # and run a series of checks on the package before we
            # start the build - most importantly license checks.

            self.log.info("Starting build: id={} builder={} job: {}"
                          .format(job.build_id, self.vm_ip, job))

            build_logger = create_file_logger(
                "{}.builder.mr".format(self.logger_name),
                job.chroot_log_path, fmt=build_log_format)

            try:
                mr = MockRemote(
                    builder_host=self.vm_ip,
                    job=job,
                    logger=build_logger,
                    opts=self.opts
                )
                mr.check()

                build_details = mr.build_pkg_and_process_results()
                job.update(build_details)

                if self.opts.do_sign:
                    mr.add_pubkey()

                register_build_result(self.opts)

            except MockRemoteError as e:
                # record and break
                self.log.exception(
                    "Error during the build, host={}, build_id={}, chroot={}, error: {}"
                    .format(self.vm_ip, job.build_id, job.chroot, e)
                )
                status = BuildStatus.FAILURE
                register_build_result(self.opts, failed=True)
            finally:
                # TODO: kind of ugly solution
                # we should remove handler from build loger, otherwise we would write
                # to the previous project
                for h in build_logger.handlers[:]:
                    build_logger.removeHandler(h)

            self.log.info(
                "Finished build: id={} builder={} timeout={} destdir={}"
                " chroot={} repos={}"
                .format(job.build_id, self.vm_ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos)))

            self.copy_mock_logs(job)

        job.status = status
        self._announce_end(job)
        self.update_process_title(suffix="Task: {} chroot: {} done"
                                  .format(job.build_id, job.chroot))

    def copy_mock_logs(self, job):
        if not os.path.isdir(job.results_dir):
            self.log.info("Job results dir doesn't exists, couldn't copy main log; path: {}"
                          .format(job.results_dir))
            return

        log_names = [(job.chroot_log_name, "mockchain.log.gz"),
                     (job.rsync_log_name, "rsync.log.gz")]

        for src_name, dst_name in log_names:
            src = os.path.join(job.chroot_dir, src_name)
            dst = os.path.join(job.results_dir, dst_name)
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
        title = "worker-{} {} ".format(self.group_name, self.worker_num)
        if self.vm_ip:
            title += "VM_IP={} ".format(self.vm_ip)
        if self.vm_name:
            title += "VM_NAME={} ".format(self.vm_name)
        if suffix:
            title += str(suffix)

        setproctitle(title)

    def notify_job_grab_about_task_end(self, job, do_reschedule=False):
        # TODO: Current notification method is unreliable,
        # we should retask and use redis + lua for atomic acquire/release tasks
        request = {
            "action": "reschedule" if do_reschedule else "remove",
            "build_id": job.build_id,
            "task_id": job.task_id,
            "chroot": job.chroot,
        }

        self.rc.publish(JOB_GRAB_TASK_END_PUBSUB, json.dumps(request))

    def acquire_vm_for_job(self, job):
        # TODO: replace acquire/release with context manager

        self.log.info("got job: {}, acquiring VM for build".format(str(job)))
        start_vm_wait_time = time.time()
        vmd = None
        while vmd is None:
            try:
                self.update_process_title(suffix="trying to acquire VM for job {} for {}s"
                                          .format(job.task_id, time.time() - start_vm_wait_time))
                vmd = self.vmm.acquire_vm(self.group_id, job.project_owner, os.getpid(),
                                          job.task_id, job.build_id, job.chroot)
            except NoVmAvailable as error:
                self.log.debug("No VM yet: {}".format(error))
                time.sleep(self.opts.sleeptime)
                continue
            except Exception as error:
                self.log.exception("Unhandled exception during VM acquire :{}".format(error))
                break
        return vmd

    def run_cycle(self):
        self.update_process_title(suffix="trying to acquire job")

        time.sleep(self.opts.sleeptime)
        job = self.obtain_job()
        if not job:
            return

        try:
            if not self.starting_build(job):
                self.notify_job_grab_about_task_end(job)
                return
        except Exception:
            self.log.exception("Failed to check if job can be started")
            self.notify_job_grab_about_task_end(job)
            return

        vmd = self.acquire_vm_for_job(job)

        if vmd is None:
            self.notify_job_grab_about_task_end(job, do_reschedule=True)
        else:
            self.log.info("acquired VM: {} ip: {} for build {}".format(vmd.vm_name, vmd.vm_ip, job.task_id))
            # TODO: store self.vmd = vmd and use it
            self.vm_name = vmd.vm_name
            self.vm_ip = vmd.vm_ip

            try:
                self.do_job(job)
                self.notify_job_grab_about_task_end(job)
            except VmError as error:
                self.log.exception("Builder error, re-scheduling task: {}".format(error))
                self.notify_job_grab_about_task_end(job, do_reschedule=True)
            except Exception as error:
                self.log.exception("Unhandled build error: {}".format(error))
                self.notify_job_grab_about_task_end(job, do_reschedule=True)
            finally:
                # clean up the instance
                self.vmm.release_vm(vmd.vm_name)
                self.vm_ip = None
                self.vm_name = None

    def run(self):
        self.log.info("Starting worker")
        self.init_fedmsg()
        self.vmm.post_init()

        self.rc = get_redis_connection(self.opts)
        self.update_process_title(suffix="trying to acquire job")
        while not self.kill_received:
            self.run_cycle()
