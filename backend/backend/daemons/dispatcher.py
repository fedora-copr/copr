import re
import os
import sys
import time
import fcntl
import json
import subprocess
from subprocess import CalledProcessError
import multiprocessing

import ansible
import ansible.runner
import ansible.utils
from ansible import callbacks
from ansible.errors import AnsibleError

from setproctitle import setproctitle
from IPy import IP
from retask.queue import Queue

from ..mockremote.callback import CliLogCallBack

from ..exceptions import MockRemoteError, CoprWorkerError, CoprWorkerSpawnFailError
from ..job import BuildJob

from ..mockremote import MockRemote
from ..frontend import FrontendClient
from ..constants import BuildStatus

ansible_playbook = "ansible-playbook"

try:
    import fedmsg
except ImportError:
    # fedmsg is optional
    fedmsg = None


def ans_extra_vars_encode(extra_vars, name):
    """ transform dict into --extra-vars="json string" """
    if not extra_vars:
        return ""
    return "--extra-vars='{{\"{0}\": {1}}}'".format(name, json.dumps(extra_vars))


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

    Worker listens for the new tasks from :py:class:`retask.Queueu` associated with its group_id

    :param Bunch opts: backend config
    :param queue: (:py:class:`multiprocessing.Queue`) queue to announce new events
    :param int worker_num: worker number
    :param int group_id: group_id from the set of groups defined in config
    :param callback: callback object to handle internal workers events. Should implement method ``log(msg)``.
    :param lock: (:py:class:`multiprocessing.Lock`) global backend lock

    """

    def __init__(self, opts, events, worker_num, group_id,
                 callback=None, lock=None):

        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")

        # job management stuff
        self.task_queue = Queue("copr-be-{0}".format(str(group_id)))
        self.task_queue.connect()
        # event queue for communicating back to dispatcher
        self.events = events
        self.worker_num = worker_num
        self.group_id = group_id
        self.vm_name = None
        self.opts = opts
        self.kill_received = False

        self.lock = lock
        self.spawn_in_advance = self.opts.spawn_in_advance
        self.frontend_callback = FrontendClient(opts, events)

        self.callback = callback
        if not self.callback:
            log_name = "worker-{0}-{1}.log".format(
                self.opts.build_groups[self.group_id]["name"],
                self.worker_num)

            self.logfile = os.path.join(self.opts.worker_logdir, log_name)
            self.callback = WorkerCallback(logfile=self.logfile)

        self.callback.log("creating worker: dynamic ip")

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

    def _announce_start(self, job, ip="none"):
        """
        Announce everywhere that a build process started now.
        """
        job.started_on = time.time()
        self.mark_started(job)

        template = "build start: user:{user} copr:{copr}" \
            " build:{build} ip:{ip}  pid:{pid}"

        content = dict(user=job.submitter, copr=job.project_name,
                       owner=job.project_owner,
                       build=job.build_id, ip=ip, pid=self.pid)
        self.event("build.start", template, content)

        template = "chroot start: chroot:{chroot} user:{user}" \
            "copr:{copr} build:{build} ip:{ip}  pid:{pid}"

        content = dict(chroot=job.chroot, user=job.submitter,
                       owner=job.project_owner,
                       copr=job.project_name, build=job.build_id,
                       ip=ip, pid=self.pid)

        self.event("chroot.start", template, content)

    def _announce_end(self, job, ip="none"):
        """
        Announce everywhere that a build process ended now.
        """
        job.ended_on = time.time()

        self.return_results(job)
        self.callback.log("worker finished build: {0}".format(ip))
        template = "build end: user:{user} copr:{copr} build:{build}" \
            " ip:{ip}  pid:{pid} status:{status}"

        content = dict(user=job.submitter, copr=job.project_name,
                       owner=job.project_owner,
                       build=job.build_id, ip=ip, pid=self.pid,
                       status=job.status, chroot=job.chroot)
        self.event("build.end", template, content)

    def run_ansible_playbook(self, args, name="running playbook", attempts=9):
        """
        Call ansible playbook:

            - well mostly we run out of space in OpenStack so we rather try
              multiple times (attempts param)
            - dump any attempt failure
        """

        # Ansible playbook python API does not work here, dunno why.  See:
        # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

        command = "{0} {1}".format(ansible_playbook, args)

        result = None
        for i in range(0, attempts):
            try:
                attempt_desc = ": retry: " if i > 0 else ": begin: "
                self.callback.log(name + attempt_desc + command)
                result = subprocess.check_output(command, shell=True)
                self.callback.log("Raw playbook output:\n{0}\n".format(result))
                break

            except CalledProcessError as e:
                self.callback.log("CalledProcessError: \n{0}\n".format(e.output))
                sys.stderr.write("{0}\n".format(e.output))
                # FIXME: this is not purpose of opts.sleeptime
                time.sleep(self.opts.sleeptime)

        self.callback.log(name + ": end")
        return result

    def validate_new_vm(self, ipaddr):
        """
        Test connectivity to the VM

        :param ipaddr: ip address to the newly created VM
        :raises: :py:class:`~backend.exceptions.CoprWorkerSpawnFailError`: validation fails
        """
        # we were getting some dead instances
        # that's why I'm testing the connectivity here
        connection = ansible.runner.Runner(
            remote_user="root",
            host_list="{},".format(ipaddr),
            pattern=ipaddr,
            forks=1,
            transport="ssh",
            timeout=500
        )
        connection.module_name = "shell"
        connection.module_args = "echo hello"

        try:
            res = connection.run()
        except Exception as exception:
            raise CoprWorkerSpawnFailError(
                "Failed to check created VM ({})"
                "due to ansible error: {}".format(ipaddr, exception))

        if ipaddr not in res.get("contacted", {}):
            self.callback.log(
                "Worker is not responding to"
                "the testing playbook. Terminating it.")
            raise CoprWorkerSpawnFailError("Created VM ({}) was unresponsive "
                                           "and therefore terminated".format(ipaddr))

    def try_spawn(self, args):
        """
        Tries to spawn new vm using ansible

        :param args: ansible for ansible command which spawns VM
        :return str: valid ip address of new machine (nobody guarantee machine availability)
        """
        result = self.run_ansible_playbook(args, "spawning instance")
        if not result:
            raise CoprWorkerSpawnFailError("No result, trying again")
        match = re.search(r'IP=([^\{\}"]+)', result, re.MULTILINE)

        if not match:
            raise CoprWorkerSpawnFailError("No ip in the result, trying again")
        ipaddr = match.group(1)
        match = re.search(r'vm_name=([^\{\}"]+)', result, re.MULTILINE)

        if match:
            self.vm_name = match.group(1)
        self.callback.log("got instance ip: {0}".format(ipaddr))

        try:
            IP(ipaddr)
        except ValueError:
            # if we get here we"re in trouble
            msg = "Invalid IP back from spawn_instance - dumping cache output\n"
            msg += str(result)
            raise CoprWorkerSpawnFailError(msg)

        return ipaddr

    def spawn_instance(self, job):
        """
        Spawn new VM, executing the following steps:

            - call the spawn playbook to startup/provision a building instance
            - get an IP and test if the builder responds
            - repeat this until you get an IP of working builder

        :param BuildJob job:
        :return ip: of created VM
        :return None: if couldn't find playbook to spin ip VM
        """

        start = time.time()

        # Ansible playbook python API does not work here, dunno why.  See:
        # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

        extra_vars = {}
        for var in self.opts.spawn_vars:
            if hasattr(job, var):
                extra_vars[var] = getattr(job, var)

        try:
            spawn_playbook = self.opts.build_groups[self.group_id]["spawn_playbook"]
        except KeyError:
            return None

        spawn_args = "-c ssh {0} {1}".format(
            spawn_playbook, ans_extra_vars_encode(extra_vars, "copr_task"))

        # TODO: replace with for i in range(MAX_SPAWN_TRIES): ... else raise FatalError
        i = 0
        while True:
            i += 1
            try:
                self.callback.log("Spawning a builder. Try No. {0}".format(i))

                ipaddr = self.try_spawn(spawn_args)
                try:
                    self.validate_new_vm(ipaddr)
                except CoprWorkerSpawnFailError:
                    self.terminate_instance(ipaddr)
                    raise

                self.callback.log("Instance spawn/provision took {0} sec"
                                  .format(time.time() - start))
                return ipaddr

            except CoprWorkerSpawnFailError as exception:
                self.callback.log("VM Spawn attemp failed with message: {}"
                                  .format(exception.msg))

    def terminate_instance(self, instance_ip):
        """
        Call the terminate playbook to destroy the building instance
        """

        term_args = {}
        if "ip" in self.opts.terminate_vars:
            term_args["ip"] = instance_ip
        if "vm_name" in self.opts.terminate_vars:
            term_args["vm_name"] = self.vm_name

        try:
            playbook = self.opts.build_groups[self.group_id]["terminate_playbook"]
        except KeyError:
            self.callback.log(
                "Fatal error: no terminate playbook for group_id: {}; exiting"
                .format(self.group_id))
            sys.exit(255)

        args = "-c ssh -i '{0},' {1} {2}".format(
            instance_ip, playbook,
            ans_extra_vars_encode(term_args, "copr_task"))
        self.run_ansible_playbook(args, "terminate instance")

    def mark_started(self, job):
        """
        Send data about started build to the frontend
        """

        job.status = 3  # running
        build = job.to_dict()
        self.callback.log("build: {}".format(build))

        data = {"builds": [build]}
        try:
            self.frontend_callback.update(data)
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
            self.frontend_callback.update(data)
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
            can_start = self.frontend_callback.starting_build(job.build_id, job.chroot)
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

    def spawn_instance_with_check(self, job):
        """
        Wrapper around self.spawn_instance() with exception checking

        :param BuildJob job:

        :return str: ip of spawned vm
        :raises:

            - :py:class:`~backend.exceptions.CoprWorkerError`: spawn function doesn't return ip
            - :py:class:`AnsibleError`: failure during anible command execution
        """
        try:
            ip = self.spawn_instance(job)
            if not ip:
                # TODO: maybe add specific exception?
                raise CoprWorkerError(
                    "No IP found from creating instance")
        except AnsibleError as e:
            self.callback.log("failure to setup instance: {0}".format(e))
            raise
        return ip

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
            "Skipping: package {0} has been already built before."
            .format(' '.join(job.pkg)))
        job.status = BuildStatus.SKIPPED  # skipped
        self._announce_end(job)

    def obtain_job(self):
        """
        Retrieves new build task from queue.
        Checks if the new job can be started and not skipped.
        """
        setproctitle("worker-{0} {1}  No task".format(
            self.opts.build_groups[self.group_id]["name"],
            self.worker_num))

        # this sometimes caused TypeError in random worker
        # when another one  picekd up a task to build
        # why?
        try:
            task = self.task_queue.dequeue()
        except TypeError:
            return
        if not task:
            return

        # import ipdb; ipdb.set_trace()
        job = BuildJob(task.data, self.opts)

        setproctitle("worker-{0} {1}  Task: {2}".format(
            self.opts.build_groups[self.group_id]["name"],
            self.worker_num, job.build_id
        ))

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

    def do_job(self, ip, job):
        """
        Executes new job.

        :param ip: ip address of the builder VM
        :param job: :py:class:`~backend.job.BuildJob`
        """
        self._announce_start(job, ip)
        status = BuildStatus.SUCCEEDED
        chroot_destdir = os.path.normpath(job.destdir + '/' + job.chroot)

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
                .format(job.build_id, ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos)))

            self.callback.log("Building pkgs: {0}".format(job.pkg))

            chroot_repos = list(job.repos)
            chroot_repos.append(job.results + '/' + job.chroot)
            # for RHBZ: #1150954
            chroot_repos.append(job.results + '/' + job.chroot + '/devel')

            chroot_logfile = "{0}/build-{1}.log".format(
                chroot_destdir, job.build_id)

            macros = {
                "copr_username": job.project_owner,
                "copr_projectname": job.project_name,
                "vendor": "Fedora Project COPR ({0}/{1})".format(
                    job.project_owner, job.project_name)
            }

            try:
                mr = MockRemote(
                    builder_host=ip, job=job, repos=chroot_repos,
                    macros=macros, opts=self.opts, lock=self.lock,
                    callback=CliLogCallBack(quiet=True, logfn=chroot_logfile),
                )
                build_details = mr.build_pkg()
                job.update(build_details)

                if self.opts.do_sign:
                    mr.add_pubkey()

            except MockRemoteError as e:
                # record and break
                self.callback.log("{0} - {1}".format(ip, e))
                status = BuildStatus.FAILURE

            self.callback.log(
                "Finished build: id={0} builder={1} timeout={2} destdir={3}"
                " chroot={4} repos={5}"
                .format(job.build_id, ip, job.timeout, job.destdir,
                        job.chroot, str(job.repos)))

        job.status = status
        self._announce_end(job, ip)

    def run(self):
        """
        Worker should startup and check if it can function
        for each job it takes from the jobs queue
        run opts.setup_playbook to create the instance
        do the build (mockremote)
        terminate the instance.

        """
        self.init_fedmsg()

        vm_ip = None
        while not self.kill_received:

            job = self.obtain_job()
            if not job:
                time.sleep(self.opts.sleeptime)
                continue

            if not vm_ip:
                vm_ip = self.spawn_instance_with_check(job)

            try:
                self.do_job(vm_ip, job)
            finally:
                # clean up the instance
                self.terminate_instance(vm_ip)
                vm_ip = None

                # TODO: since spawn requires job object to create vm
                #   it's possible to have spawned VM with incorrect configuration
                #   disabling spawn in advance for now
                #   if self.spawn_in_advance:
                #     vm_ip = self.spawn_instance_with_check(job)
