from datetime import datetime
import json
import os
import sys
import time
import fcntl
import multiprocessing
from setproctitle import setproctitle

from retask.queue import Queue

from ..vm_manage.manager import VmManager
from ..mockremote.callback import CliLogCallBack
from ..exceptions import MockRemoteError, CoprWorkerError, VmError, NoVmAvailable
from ..job import BuildJob
from ..mockremote import MockRemote
from ..constants import BuildStatus, JOB_GRAB_TASK_END_PUBSUB
from ..helpers import register_build_result, format_tb, get_redis_connection


# ansible_playbook = "ansible-playbook"

try:
    import fedmsg
except ImportError:
    # fedmsg is optional
    fedmsg = None


class WorkerCallback(object):
    """
    Callback class for worker. Now used only for message logging

    :param logfile: path to the log file
    """

    def __init__(self, logfile=None):
        self.logfile = logfile

    def log(self, msg):
        """
        Safely writes msg to the logfile

        :param str msg: message to be logged
        """
        if self.logfile:
            now = time.strftime("%F %T")
            try:
                with open(self.logfile, 'a') as lf:
                    fcntl.flock(lf, fcntl.LOCK_EX)
                    lf.write(str(now) + ': ' + msg + '\n')
                    fcntl.flock(lf, fcntl.LOCK_UN)
            except (IOError, OSError) as e:
                sys.stderr.write("Could not write to logfile {0} - {1}\n"
                                 .format(self.logfile, str(e)))


class Worker(multiprocessing.Process):
    """
    Worker process dispatches building tasks. Backend spin-up multiple workers, each
    worker associated to one group_id and process one task at the each moment.

    Worker listens for the new tasks from :py:class:`retask.Queue` associated with its group_id

    :param Bunch opts: backend config
    :param queue: (:py:class:`multiprocessing.Queue`) queue to announce new events
    :param int worker_num: worker number
    :param int group_id: group_id from the set of groups defined in config
    :param callback: callback object to handle internal workers events. Should implement method ``log(msg)``.
    :param lock: (:py:class:`multiprocessing.Lock`) global backend lock

    """

    def __init__(self, opts, events, frontend_client, worker_num, group_id,
                 callback=None, lock=None):

        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")

        self.opts = opts

        # job management stuff
        self.task_queue = Queue("copr-be-{0}".format(str(group_id)))
        self.task_queue.connect()
        # event queue for communicating back to dispatcher
        self.events = events
        self.worker_num = worker_num
        self.group_id = group_id

        self.kill_received = False
        self.lock = lock
        # self.frontend_client = FrontendClient(opts, events)
        self.frontend_client = frontend_client
        self.callback = callback
        if not self.callback:
            log_name = "worker-{0}-{1}.log".format(
                self.group_name,
                self.worker_num)

            self.logfile = os.path.join(self.opts.worker_logdir, log_name)
            self.callback = WorkerCallback(logfile=self.logfile)

        self.vm_name = None
        self.vm_ip = None
        self.callback.log("creating worker: dynamic ip")

        self.rc = None
        self.vmm = VmManager(self.opts, self.events)

    @property
    def group_name(self):
        try:
            return self.opts.build_groups[self.group_id]["name"]
        except Exception as error:
            self.callback.log("Failed to get builder group name from config, using group_id as name."
                              "Original error: {}".format(error))
            return str(self.group_id)

    def event(self, topic, template, content=None):
        """ Multi-purpose logging method.

        Logs messages to three different destinations:
            - To log file
            - The internal "events" queue for communicating back to the
              dispatcher.
            - The fedmsg bus.  Messages are posted asynchronously to a
              zmq.PUB socket.

        """

        content = content or {}
        what = template.format(**content)
        who = "worker-{0}".format(self.worker_num)

        self.callback.log("event: who: {0}, what: {1}".format(who, what))
        self.events.put({"when": time.time(), "who": who, "what": what})

        if self.opts.fedmsg_enabled and fedmsg:
            content["who"] = who
            content["what"] = what
            try:
                fedmsg.publish(modname="copr", topic=topic, msg=content)
            # pylint: disable=W0703
            except Exception as e:
                # XXX - Maybe log traceback as well with traceback.format_exc()
                self.callback.log("failed to publish message: {0}".format(e))

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
        self.event("build.start", template, content)

        template = "chroot start: chroot:{chroot} user:{user}" \
            "copr:{copr} pkg: {pkg} build:{build} ip:{ip}  pid:{pid}"

        content = dict(chroot=job.chroot, user=job.submitter,
                       owner=job.project_owner, pkg=job.pkg_name,
                       copr=job.project_name, build=job.build_id,
                       ip=self.vm_ip, pid=self.pid)

        self.event("chroot.start", template, content)

    def _announce_end(self, job):
        """
        Announce everywhere that a build process ended now.
        """
        job.ended_on = time.time()

        self.return_results(job)
        self.callback.log("worker finished build: {0}".format(self.vm_ip))
        template = "build end: user:{user} copr:{copr} build:{build}" \
            "  pkg: {pkg}  version: {version} ip:{ip}  pid:{pid} status:{status}"

        content = dict(user=job.submitter, copr=job.project_name,
                       owner=job.project_owner,
                       pkg=job.pkg_name, version=job.pkg_version,
                       build=job.build_id, ip=self.vm_ip, pid=self.pid,
                       status=job.status, chroot=job.chroot)
        self.event("build.end", template, content)

    def mark_started(self, job):
        """
        Send data about started build to the frontend
        """

        job.status = BuildStatus.RUNNING
        build = job.to_dict()
        self.callback.log("build: {}".format(build))

        data = {"builds": [build]}
        # import ipdb; ipdb.set_trace()
        try:
            self.frontend_client.update(data)
        except:
            raise CoprWorkerError(
                "Could not communicate to front end to submit status info")

    def return_results(self, job):
        """
        Send the build results to the frontend
        """
        self.callback.log(
            "{0} status {1}. Took {2} seconds".format(
                job.build_id, job.status, job.ended_on - job.started_on))

        self.callback.log("build: {}".format(job.to_dict()))
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
            self.callback.log(
                "failed to initialize fedmsg: {0}".format(e))

    def on_pkg_skip(self, job):
        """
        Handle package skip
        """
        self._announce_start(job)
        self.callback.log(
            "Skipping: package {0} has been already built before.".format(job.pkg))
        job.status = BuildStatus.SKIPPED  # skipped
        self.notify_job_grab_about_task_end(job)
        self._announce_end(job)

    def obtain_job(self):
        """
        Retrieves new build task from queue.
        Checks if the new job can be started and not skipped.
        """
        self.update_process_title(suffix="No task")

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

        # Checking whether the build is not cancelled
        if not self.starting_build(job):
            return

        # Checking whether to build or skip
        if self.pkg_built_before(job.pkg, job.chroot, job.destdir):
            self.on_pkg_skip(job)
            return

        # FIXME
        # this is our best place to sanity check the job before starting
        # up any longer process

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

                self.callback.log(msg)
                status = BuildStatus.FAILURE

        if status == BuildStatus.SUCCEEDED:
            # FIXME
            # need a plugin hook or some mechanism to check random
            # info about the pkgs
            # this should use ansible to download the pkg on
            # the remote system
            # and run a series of checks on the package before we
            # start the build - most importantly license checks.

            self.callback.log(
                "Starting build: id={0} builder={1} timeout={2} destdir={3}"
                " chroot={4} repos={5}"
                .format(job.build_id, self.vm_ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos)))

            self.callback.log("Building pkgs: {0}".format(job.pkg))

            chroot_repos = list(job.repos)
            chroot_repos.append(job.results + job.chroot + '/')
            chroot_repos.append(job.results + job.chroot + '/devel/')

            chroot_logfile = "{0}/build-{1}.log".format(
                chroot_destdir, job.build_id)

            try:
                mr = MockRemote(
                    builder_host=self.vm_ip, job=job, repos=chroot_repos,
                    opts=self.opts, lock=self.lock,
                    callback=CliLogCallBack(quiet=True, logfn=chroot_logfile),
                )
                mr.check()

                build_details = mr.build_pkg_and_process_results()
                job.update(build_details)

                if self.opts.do_sign:
                    mr.add_pubkey()

                register_build_result(self.opts)

            #except VmError as e:
            #    pass
            # don't catch VmError
            except MockRemoteError as e:
                # record and break
                self.callback.log("{0} - {1}".format(self.vm_ip, e))
                status = BuildStatus.FAILURE
                register_build_result(self.opts, failed=True)

            self.callback.log(
                "Finished build: id={0} builder={1} timeout={2} destdir={3}"
                " chroot={4} repos={5}"
                .format(job.build_id, self.vm_ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos)))

        job.status = status
        self._announce_end(job)
        self.update_process_title(suffix="Task: {} chroot: {} done"
                                  .format(job.build_id, job.chroot))

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
        request = {
            "action": "reschedule" if do_reschedule else "remove",
            "build_id": job.build_id,
            "task_id": job.task_id,
            "chroot": job.chroot,
        }

        self.rc.publish(JOB_GRAB_TASK_END_PUBSUB, json.dumps(request))

    def run_cycle(self):
        self.update_process_title(suffix="trying to acquire job")

        # self.callback.log("Trying to obtain a job ")
        job = self.obtain_job()
        if not job:
            time.sleep(self.opts.sleeptime)
            return

        start_vm_wait_time = time.time()
        vmd = None
        while vmd is None:
            try:
                self.update_process_title(suffix="trying to acquire VM for job {} for {}s"
                                          .format(job.task_id, time.time() - start_vm_wait_time))
                vmd = self.vmm.acquire_vm(self.group_id, job.project_owner, os.getpid(),
                                          job.task_id, job.build_id, job.chroot)
            except NoVmAvailable as error:
                self.callback.log("No VM yet: {}".format(error))
                time.sleep(self.opts.sleeptime)
                continue
            except Exception as error:
                _, _, ex_tb = sys.exc_info()
                self.callback.log("Unhandled exception during VM acquire :{}, {}".format(error, format_tb(error, ex_tb)))
                self.notify_job_grab_about_task_end(job, do_reschedule=True)
                time.sleep(self.opts.sleeptime)
                return

        try:
            # got vmd
            # TODO: store self.vmd = vmd and use it
            self.vm_name = vmd.vm_name
            self.vm_ip = vmd.vm_ip

            self.do_job(job)
            self.notify_job_grab_about_task_end(job)
        except VmError as error:
            _, _, ex_tb = sys.exc_info()
            self.callback.log("Builder error, re-scheduling task: {}, {}".format(error, format_tb(error, ex_tb)))
            self.notify_job_grab_about_task_end(job, do_reschedule=True)
        except Exception as error:
            _, _, ex_tb = sys.exc_info()
            self.callback.log("Unhandled build error: {}, {}".format(error, format_tb(error, ex_tb)))
            self.notify_job_grab_about_task_end(job, do_reschedule=True)
        finally:
            # clean up the instance
            self.vmm.release_vm(vmd.vm_name)
            self.vm_ip = None
            self.vm_name = None

    def run(self):
        self.init_fedmsg()
        self.vmm.post_init()

        self.rc = get_redis_connection(self.opts)
        self.update_process_title(suffix="trying to acquire job")
        while not self.kill_received:
            self.run_cycle()
