from datetime import datetime
import json
import logging
import os
import sys
import time
import fcntl
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

    :param Bunch opts: backend config
    :param int worker_num: worker number
    :param int group_id: group_id from the set of groups defined in config
    :param lock: (:py:class:`multiprocessing.Lock`) global backend lock

    """

    def __init__(self, opts, frontend_client, worker_num, group_id, lock=None):

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
        self.lock = lock

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
                       owner=job.project_owner, pkg=job.pkg_name,
                       build=job.build_id, ip=self.vm_ip, pid=self.pid)
        self.fedmsg_notify("build.start", template, content)

        template = "chroot start: chroot:{chroot} user:{user}" \
            "copr:{copr} pkg: {pkg} build:{build} ip:{ip}  pid:{pid}"

        content = dict(chroot=job.chroot, user=job.submitter,
                       owner=job.project_owner, pkg=job.pkg_name,
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
                       pkg=job.pkg_name, version=job.pkg_version,
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

        :return True: if the build can start
        :return False: if the build can not start (build is cancelled)
        """

        try:
            can_start = self.frontend_client.starting_build(job.build_id, job.chroot)
        except Exception as err:
            raise CoprWorkerError(
                "Could not communicate to front end to submit results: {}"
                .format(err)
            )

        return can_start

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

    def on_pkg_skip(self, job):
        """
        Handle package skip
        """
        self._announce_start(job)
        self.log.info("Skipping: package {} has been already built before.".format(job.pkg))
        job.status = BuildStatus.SKIPPED
        self.notify_job_grab_about_task_end(job)
        self._announce_end(job)

    def can_start_job(self, job):
        """
        Checks if we can and/or should start job
        :type job: BuildJob
        :rtype: bool
        """
        # Checking whether the build is not cancelled
        if not self.starting_build(job):
            self.log.info("Couldn't start job: {}".format(job))
            return False

        # Checking whether to build or skip
        if self.pkg_built_before(job.pkg, job.chroot, job.destdir):
            self.on_pkg_skip(job)
            return False

        return True

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
        self.update_process_title(suffix="Task: {} chroot: {} build started".format(job.build_id, job.chroot))
        status = BuildStatus.SUCCEEDED
        chroot_destdir = os.path.normpath("{}/{}".format(job.destdir, job.chroot))

        # setup our target dir locally
        if not os.path.exists(chroot_destdir):
            try:
                os.makedirs(chroot_destdir)
            except (OSError, IOError) as e:
                msg = "Could not make results dir" \
                      " for job: {0} - {1}".format(chroot_destdir, str(e))

                self.log.exception(msg)
                status = BuildStatus.FAILURE

        pdn = os.path.basename(job.pkg).replace(".src.rpm", "")
        resdir = os.path.join(chroot_destdir, pdn)
        if os.path.exists(resdir) and os.listdir(resdir) != []:
            # Target have already been attempted to build
            # We should backup the results and clean the directory
            self._clean_result_directory(resdir)

        if status == BuildStatus.SUCCEEDED:
            # FIXME
            # need a plugin hook or some mechanism to check random
            # info about the pkgs
            # this should use ansible to download the pkg on
            # the remote system
            # and run a series of checks on the package before we
            # start the build - most importantly license checks.

            self.log.info(
                "Starting build: id={} builder={} timeout={} destdir={}"
                " chroot={} repos={} pkg={}"
                .format(job.build_id, self.vm_ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos), job.pkg))

            chroot_repos = list(job.repos)
            chroot_repos.append(job.results + job.chroot + '/')
            chroot_repos.append(job.results + job.chroot + '/devel/')

            chroot_logfile = "{}/build-{:08d}.log".format(chroot_destdir, job.build_id)

            build_logger = create_file_logger("{}.builder.mr".format(self.logger_name),
                                              chroot_logfile, fmt=build_log_format)
            try:
                mr = MockRemote(
                    builder_host=self.vm_ip, job=job,
                    logger=build_logger,
                    repos=chroot_repos,
                    opts=self.opts, lock=self.lock,
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

        job.status = status
        self._announce_end(job)
        self.update_process_title(suffix="Task: {} chroot: {} done"
                                  .format(job.build_id, job.chroot))

    def _clean_result_directory(self, resdir):
        """
        Create backup directory and move there results from previous build.
        Backup directory will be called ``build-<id>`` and located in result directory
        """
        backupdir = os.path.join(resdir, "prev_build_backup")
        self.log.info("Cleaning target directory, results from previous build storing in {}"
                      .format(backupdir))

        if not os.path.exists(backupdir):
            os.makedirs(backupdir)

        for filename in os.listdir(resdir):
            if os.path.isfile(os.path.join(resdir, filename)):
                os.rename(os.path.join(resdir, filename), os.path.join(backupdir, filename))

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
            if not self.can_start_job(job):
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
