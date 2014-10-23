import re
import os
import sys
import time
import fcntl
import json
import subprocess
import multiprocessing

import ansible
import ansible.runner
import ansible.utils
from ansible import callbacks
from bunch import Bunch
from setproctitle import setproctitle
from IPy import IP
from retask.queue import Queue
from .exceptions import MockRemoteError, CoprWorkerError

import mockremote
from callback import FrontendCallback

ansible_playbook = "ansible-playbook"

try:
    import fedmsg
except ImportError:
    pass  # fedmsg is optional

def ans_extra_vars_encode(extra_vars, name):
    """ transform dict into --extra-vars="json string" """
    if not extra_vars:
        return ""
    return "--extra-vars='{{\"{0}\": {1}}}'".format(
            name, json.dumps(extra_vars))

class SilentPlaybookCallbacks(callbacks.PlaybookCallbacks):

    """ playbook callbacks - quietly! """

    def __init__(self, verbose=False):
        super(SilentPlaybookCallbacks, self).__init__()
        self.verbose = verbose

    @classmethod
    def on_start(cls):
        callbacks.call_callback_module("playbook_on_start")

    @classmethod
    def on_notify(cls, host, handler):
        callbacks.call_callback_module("playbook_on_notify", host, handler)

    @classmethod
    def on_no_hosts_matched(cls):
        callbacks.call_callback_module("playbook_on_no_hosts_matched")

    @classmethod
    def on_no_hosts_remaining(cls):
        callbacks.call_callback_module("playbook_on_no_hosts_remaining")

    @classmethod
    def on_task_start(cls, name, is_conditional):
        callbacks.call_callback_module(
            "playbook_on_task_start", name, is_conditional)

    @classmethod
    def on_vars_prompt(cls, varname,
                       private=True, prompt=None, encrypt=None,
                       confirm=False, salt_size=None, salt=None):

        result = None
        sys.stderr.write(
            "***** VARS_PROMPT WILL NOT BE RUN IN THIS KIND OF PLAYBOOK *****\n")

        callbacks.call_callback_module(
            "playbook_on_vars_prompt", varname, private=private,
            prompt=prompt, encrypt=encrypt, confirm=confirm,
            salt_size=salt_size, salt=None)

        return result

    @classmethod
    def on_setup(cls):
        callbacks.call_callback_module("playbook_on_setup")

    @classmethod
    def on_import_for_host(cls, host, imported_file):
        callbacks.call_callback_module(
            "playbook_on_import_for_host", host, imported_file)

    @classmethod
    def on_not_import_for_host(cls, host, missing_file):
        callbacks.call_callback_module(
            "playbook_on_not_import_for_host", host, missing_file)

    @classmethod
    def on_play_start(cls, pattern):
        callbacks.call_callback_module("playbook_on_play_start", pattern)

    @classmethod
    def on_stats(cls, stats):
        callbacks.call_callback_module("playbook_on_stats", stats)


class WorkerCallback(object):

    def __init__(self, logfile=None):
        self.logfile = logfile

    def log(self, msg):
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

    def __init__(self, opts, events, worker_num, group_id,
                 ip=None, create=True, callback=None, lock=None):

        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")

        # job management stuff
        self.task_queue = Queue("copr-be-{0}".format(str(group_id)))
        self.task_queue.connect()
        # event queue for communicating back to dispatcher
        self.events = events
        self.worker_num = worker_num
        self.group_id = group_id
        self.ip = ip
        self.vm_name = None
        self.opts = opts
        self.kill_received = False
        self.callback = callback
        self.create = create
        self.lock = lock
        self.frontend_callback = FrontendCallback(opts)
        if not self.callback:
            self.logfile = os.path.join(
                self.opts.worker_logdir,
                "worker-{0}-{1}.log".format(
                            self.opts.build_groups[self.group_id]["name"],
                            self.worker_num))
            self.callback = WorkerCallback(logfile=self.logfile)

        if ip:
            self.callback.log("creating worker: {0}".format(ip))
        else:
            self.callback.log("creating worker: dynamic ip")

    def event(self, topic, template, content=None):
        """ Multi-purpose logging method.

        Logs messages to two different destinations:
            - To log file
            - The internal "events" queue for communicating back to the
              dispatcher.
            - The fedmsg bus.  Messages are posted asynchronously to a
              zmq.PUB socket.

        """

        content = content or {}
        what = template.format(**content)

        if self.ip:
            who = "worker-{0}-{1}".format(self.worker_num, self.ip)
        else:
            who = "worker-{0}".format(self.worker_num)

        self.callback.log("event: who: {0}, what: {1}".format(who, what))
        self.events.put({"when": time.time(), "who": who, "what": what})
        try:
            content["who"] = who
            content["what"] = what
            if self.opts.fedmsg_enabled:
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
        call ansible playbook
            - well mostly we run out of space in OpenStack so we rather try
              multiple times (attempts param)
            - dump any attempt failure
        """

        # Ansible playbook python API does not work here, dunno why.  See:
        # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

        command = "{0} {1}".format(ansible_playbook, args)

        for i in range(0, attempts):
            try:
                attempt_desc = ": retry: " if i else ": begin: "
                self.callback.log(name + attempt_desc + command)

                result = subprocess.check_output(command, shell=True)
                self.callback.log("Raw playbook output:\n{0}\n".format(result))
                break

            except subprocess.CalledProcessError as e:
                result = None
                self.callback.log("CalledProcessError: \n{0}\n".format(e.output))
                sys.stderr.write("{0}\n".format(e.output))
                # FIXME: this is not purpose of opts.sleeptime
                time.sleep(self.opts.sleeptime)

        self.callback.log(name + ": end")
        return result

    def spawn_instance(self, job):
        """
        call the spawn playbook to startup/provision a building instance
        get an IP and test if the builder responds
        repeat this until you get an IP of working builder
        """

        start = time.time()

        # Ansible playbook python API does not work here, dunno why.  See:
        # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

        extra_vars = {}
        if self.opts.spawn_vars:
            for i in self.opts.spawn_vars.split(","):
                if i == 'chroot':
                    extra_vars['chroot'] = job['chroot']

        try:
            spawn_playbook = self.opts.build_groups[self.group_id]["spawn_playbook"]
        except KeyError:
            return None

        args = "-c ssh {0} {1}".format(
                spawn_playbook,
                ans_extra_vars_encode(extra_vars, "copr_task"))

        i = 0
        while True:
            i += 1
            self.callback.log("Spawning a builder. Try No. {0}".format(i))
            result = self.run_ansible_playbook(args, "spawning instance")
            if not result:
                self.callback.log("No result, trying again")
                continue

            match = re.search(r'IP=([^\{\}"]+)', result, re.MULTILINE)
            if not match:
                self.callback.log("No ip in the result, trying again")
                continue
            ipaddr = match.group(1)

            match = re.search(r'vm_name=([^\{\}"]+)', result, re.MULTILINE)
            if match:
                self.vm_name = match.group(1)

            self.callback.log("got instance ip: {0}".format(ipaddr))
            self.callback.log(
                "Instance spawn/provision took {0} sec".format(time.time() - start))

            try:
                IP(ipaddr)
            except ValueError:
                # if we get here we"re in trouble
                self.callback.log(
                    "Invalid IP back from spawn_instance - dumping cache output")
                self.callback.log(str(result))
                continue

            # we were getting some dead instancies
            # that's why I'm testing the conncectivity here
            connection = ansible.runner.Runner(
                            remote_user="root",
                            host_list=ipaddr+",",
                            pattern=ipaddr,
                            forks=1,
                            transport="ssh",
                            timeout=500)
            connection.module_name = "shell"
            connection.module_args = "echo hello"
            res = connection.run()

            if res["contacted"]:
                return ipaddr

            else:
                self.callback.log("Worker is not responding to" \
                        "the testing playbook. Spawning another one.")
                self.terminate_instance(ipaddr)


    def terminate_instance(self, instance_ip):
        """call the terminate playbook to destroy the building instance"""

        term_args = {}
        if self.opts.terminate_vars:
            for i in self.opts.terminate_vars.split(","):
                if i == "ip":
                    term_args["ip"] = instance_ip
                if i == "vm_name":
                    term_args["vm_name"] = self.vm_name

        args = "-c ssh -i '{0},' {1} {2}".format(
                instance_ip, self.opts.build_groups[self.group_id]["terminate_playbook"],
                ans_extra_vars_encode(term_args, "copr_task"))
        self.run_ansible_playbook(args, "terminate instance")


    def create_job(self, task):
        """
        Create a Bunch from the task dict and add some stuff
        """
        job = Bunch()
        job.update(task)

        job.pkgs = [task["pkgs"]] # just for now

        job.repos = [r for r in task["repos"].split(" ") if r.strip()]

        if not task["timeout"]:
            job.timeout = self.opts.timeout

        job.destdir = os.path.normpath(
            os.path.join(self.opts.destdir,
                task["project_owner"],
                task["project_name"]))

        job.results = os.path.join(
            self.opts.results_baseurl,
            task["project_owner"],
            task["project_name"] + "/")

        job.pkg_version = ""
        job.built_packages = ""

        return job


    def mark_started(self, job):
        """
        Send data about started build to the frontend
        """
        build = {"id": job.build_id,
                 "started_on": job.started_on,
                 "results": job.results,
                 "chroot": job.chroot,
                 "status": 3,  # running
                 }
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

        build = {
            "id": job.build_id,
            "ended_on": job.ended_on,
            "status": job.status,
            "chroot": job.chroot,
            "pkg_version": job.pkg_version,
            "built_packages": job.built_packages,
        }

        data = {"builds": [build]}

        try:
            self.frontend_callback.update(data)
        except:
            raise CoprWorkerError(
                "Could not communicate to front end to submit results")


    def starting_build(self, job):
        """
        Announce to the frontend that a build is starting.
        Return: True if the build can start
                False if the build can not start (build is cancelled)
        """
        response = None
        try:
            response = self.frontend_callback.starting_build(
                                                    job.build_id,
                                                    job.chroot)
        except:
            raise CoprWorkerError(
                "Could not communicate to front end to submit results")

        return response


    @classmethod
    def pkg_built_before(cls, pkgs, chroot, destdir):
        """
        Check whether the package has already been built in this chroot.
        """
        s_pkg = os.path.basename(pkgs[0])
        pdn = s_pkg.replace(".src.rpm", "")
        resdir = "{0}/{1}/{2}".format(destdir, chroot, pdn)
        resdir = os.path.normpath(resdir)
        if os.path.exists(resdir):
            if os.path.exists(os.path.join(resdir, "success")):
                return True
        return False

    def run(self):
        """
        Worker should startup and check if it can function
        for each job it takes from the jobs queue
        run opts.setup_playbook to create the instance
        do the build (mockremote)
        terminate the instance.
        """

        while not self.kill_received:
            setproctitle("worker-{0} {1}  No task".format(
                        self.opts.build_groups[self.group_id]["name"],
                        self.worker_num))

            # this sometimes caused TypeError in random worker
            # when another one  picekd up a task to build
            # why?
            try:
                task = self.task_queue.dequeue()
            except TypeError:
                pass

            if not task:
                time.sleep(self.opts.sleeptime)
                continue

            job = self.create_job(task.data)

            setproctitle("worker-{0} {1}  Task: {2}".format(
                        self.opts.build_groups[self.group_id]["name"],
                        self.worker_num,
                        job.task_id))

            # Checking whether the build is not cancelled
            if not self.starting_build(job):
                continue

            # Initialize Fedmsg
            # (this assumes there are certs and a fedmsg config on disk)
            try:
                if self.opts.fedmsg_enabled:
                    fedmsg.init(
                        name="relay_inbound",
                        cert_prefix="copr",
                        active=True)

            except Exception as e:
                self.callback.log(
                    "failed to initialize fedmsg: {0}".format(e))

            # Checking whether to build or skip
            if self.pkg_built_before(job.pkgs, job.chroot, job.destdir):
                self._announce_start(job)
                self.callback.log("Skipping: package {0} has been"\
                            "already built before.".format(
                            ' '.join(job.pkgs)))
                job.status = 5 # skipped
                self._announce_end(job)
                continue
            # FIXME
            # this is our best place to sanity check the job before starting
            # up any longer process

            # spin up our build instance
            if self.create and not self.ip:
                try:
                    ip = self.spawn_instance(job)
                    if not ip:
                        raise CoprWorkerError(
                            "No IP found from creating instance")

                except ansible.errors.AnsibleError as e:
                    self.callback.log(
                        "failure to setup instance: {0}".format(e))
                    raise
            else:
                ip = self.ip

            try:
                self._announce_start(job, ip)

                status = 1  # succeeded

                chroot_destdir = os.path.normpath(
                    job.destdir + '/' + job.chroot)

                # setup our target dir locally
                if not os.path.exists(chroot_destdir):
                    try:
                        os.makedirs(chroot_destdir)
                    except (OSError, IOError) as e:
                        msg = "Could not make results dir" \
                              " for job: {0} - {1}".format(chroot_destdir,
                                                           str(e))

                        self.callback.log(msg)
                        status = 0  # fail

                if status == 1:  # succeeded
                    # FIXME
                    # need a plugin hook or some mechanism to check random
                    # info about the pkgs
                    # this should use ansible to download the pkg on
                    # the remote system
                    # and run a series of checks on the package before we
                    # start the build - most importantly license checks.

                    self.callback.log("Starting build: id={0} builder={1}"
                                      " timeout={2} destdir={3}"
                                      " chroot={4} repos={5}".format(
                                          job.build_id, ip,
                                          job.timeout, job.destdir,
                                          job.chroot, str(job.repos)))

                    self.callback.log("building pkgs: {0}".format(
                        ' '.join(job.pkgs)))

                    try:
                        chroot_repos = list(job.repos)
                        chroot_repos.append(job.results + '/' + job.chroot)
                        # for RHBZ: #1150954
                        chroot_repos.append(job.results + '/' + job.chroot + '/devel')

                        chrootlogfile = "{0}/build-{1}.log".format(
                            chroot_destdir, job.build_id)

                        macros = {
                            "copr_username": job.project_owner,
                            "copr_projectname": job.project_name,
                            "vendor": "Fedora Project COPR ({0}/{1})".format(
                                job.project_owner, job.project_name)
                        }

                        mr = mockremote.MockRemote(
                            builder=ip,
                            timeout=job.timeout,
                            destdir=job.destdir,
                            chroot=job.chroot,
                            cont=True,
                            recurse=True,
                            repos=chroot_repos,
                            macros=macros,
                            lock=self.lock,
                            do_sign=self.opts.do_sign,
                            build_id=job.build_id,
                            buildroot_pkgs=job.buildroot_pkgs,
                            callback=mockremote.CliLogCallBack(
                                quiet=True, logfn=chrootlogfile),
                            front_url=self.opts.frontend_base_url,
                        )

                        build_details = mr.build_pkgs(job.pkgs)

                        if self.opts.do_sign:
                            mr.add_pubkey(os.path.normpath(
                                os.path.join(job.destdir, job.chroot)))

                        job.update(build_details)

                    except MockRemoteError as e:
                        # record and break
                        self.callback.log("{0} - {1}".format(ip, e))
                        status = 0  # failure
                    else:
                        # we can"t really trace back if we just fail normally
                        # check if any pkgs didn"t build
                        if mr.failed:
                            status = 0  # failure

                    self.callback.log(
                        "Finished build: id={0} builder={1}"
                        " timeout={2} destdir={3}"
                        " chroot={4} repos={5}".format(
                            job.build_id, ip,
                            job.timeout, job.destdir,
                            job.chroot, str(job.repos)))

                job.status = status
                self._announce_end(job, ip)

            finally:
                # clean up the instance
                if self.create:
                    self.terminate_instance(ip)
