# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import grp
import multiprocessing
import os
import pwd
import signal
import sys
import time
from collections import defaultdict

import lockfile
from daemon import DaemonContext
from retask.queue import Queue
from retask import ConnectionError
from backend.frontend import FrontendClient

from ..exceptions import CoprBackendError
from ..helpers import BackendConfigReader
from .job_grab import CoprJobGrab
from .log import CoprBackendLog
from .dispatcher import Worker

from .vm_master import VmMaster

from ..vm_manage.manager import VmManager
from ..vm_manage.spawn import Spawner
from ..vm_manage.check import HealthChecker
from ..vm_manage.terminate import Terminator


class CoprBackend(object):

    """
    Core process - starts/stops/initializes workers and other backend components


    :param config_file: path to the backend configuration file
    :param ext_opts: additional options for backend
    """

    def __init__(self, config_file=None, ext_opts=None):
        # read in config file
        # put all the config items into a single self.opts bunch

        if not config_file:
            raise CoprBackendError("Must specify config_file")

        self.config_file = config_file
        self.ext_opts = ext_opts  # to stow our cli options for read_conf()
        self.workers_by_group_id = defaultdict(list)
        self.max_worker_num_by_group_id = defaultdict(int)

        self.config_reader = BackendConfigReader(self.config_file, self.ext_opts)
        self.opts = None
        self.update_conf()

        self.lock = multiprocessing.Lock()

        self.task_queues = {}
        self.events = multiprocessing.Queue()
        # event format is a dict {when:time, who:[worker|logger|job|main],
        # what:str}
        self.frontend_client = FrontendClient(self.opts, self.events)
        self.abort = False
        if not os.path.exists(self.opts.worker_logdir):
            os.makedirs(self.opts.worker_logdir, mode=0o750)

    def clean_task_queues(self):
        """
        Make sure there is nothing in our task queues
        """
        try:
            for queue in self.task_queues.values():
                while queue.length:
                    queue.dequeue()
        except ConnectionError:
            raise CoprBackendError(
                "Could not connect to a task queue. Is Redis running?")

    def init_task_queues(self):
        """
        Connect to the retask.Queue for each group_id. Remove old tasks from queues.
        """
        try:
            for group in self.opts.build_groups:
                group_id = group["id"]
                queue = Queue("copr-be-{0}".format(group_id))
                queue.connect()
                self.task_queues[group_id] = queue
        except ConnectionError:
            raise CoprBackendError(
                "Could not connect to a task queue. Is Redis running?")

        self.clean_task_queues()

    def init_sub_process(self):
        """
        - Create backend logger
        - Create job grabber
        """
        self._logger = CoprBackendLog(self.opts, self.events)
        self._logger.start()

        self.event("Starting up Job Grabber")

        self._jobgrab = CoprJobGrab(opts=self.opts,
                                    events=self.events,
                                    frontend_client=self.frontend_client,
                                    lock=self.lock)
        self._jobgrab.start()

        self.spawner = Spawner(self.opts, self.events)
        self.checker = HealthChecker(self.opts, self.events)
        self.terminator = Terminator(self.opts, self.events)

        self.vm_manager = VmManager(self.opts, self.events,
                                    checker=self.checker,
                                    spawner=self.spawner,
                                    terminator=self.terminator)
        self.vm_manager.post_init()
        self.vmm_daemon = VmMaster(self.vm_manager)
        self.vmm_daemon.start()

    def event(self, what):
        """
        Put a new event into the queue
        :param what: Event content
        """
        self.events.put({"when": time.time(), "who": "main", "what": what})

    def update_conf(self):
        """
        Update backend config from config file
        """
        self.opts = self.config_reader.read()

    def spin_up_workers_by_group(self, group):
        """
        Handles starting/growing the number of workers

        :param dict group: Builders group

        Utilized keys:
            - **id**
            - **max_workers**

        """
        group_id = group["id"]

        if len(self.workers_by_group_id[group_id]) < group["max_workers"]:
            self.event("Spinning up more workers")
            for _ in range(group["max_workers"] - len(self.workers_by_group_id[group_id])):
                self.max_worker_num_by_group_id[group_id] += 1
                w = Worker(
                    opts=self.opts,
                    events=self.events,
                    frontend_client=self.frontend_client,
                    worker_num=self.max_worker_num_by_group_id[group_id],
                    group_id=group_id,
                    lock=self.lock
                )

                self.workers_by_group_id[group_id].append(w)
                w.start()

    def prune_dead_workers_by_group_id(self, group_id):
        """ Removes dead workers from the pool

        :return list: alive workers

        :raises:
            :py:class:`~backend.exceptions.CoprBackendError` when got dead worker and
                option "exit_on_worker" is enabled
        """
        preserved_workers = []
        for w in self.workers_by_group_id[group_id]:
            if not w.is_alive():
                self.event("Worker {0} died unexpectedly".format(w.worker_num))
                w.terminate()  # kill it with a fire
                if self.opts.exit_on_worker:
                    raise CoprBackendError(
                        "Worker died unexpectedly, exiting")
            else:
                preserved_workers.append(w)
        return preserved_workers

    def terminate(self):
        """
        Cleanup backend processes (just workers for now)
        And also clean all task queues as they would survive copr restart
        """

        self.abort = True
        for group in self.opts.build_groups:
            group_id = group["id"]
            for w in self.workers_by_group_id[group_id][:]:
                self.workers_by_group_id[group_id].remove(w)
                w.terminate_instance()
        self.clean_task_queues()

    def run(self):
        """
        Starts backend process. Control sub process start/stop.
        """
        self.init_task_queues()
        self.init_sub_process()

        self.abort = False
        while not self.abort:
            # re-read config into opts
            self.update_conf()

            for group in self.opts.build_groups:
                group_id = group["id"]
                self.event("# jobs in {0} queue: {1}"
                           .format(group["name"], self.task_queues[group_id].length))
                self.spin_up_workers_by_group(group)
                self.event("Finished starting worker processes")

                # FIXME - prune out workers
                # if len(self.workers) > self.opts.num_workers:
                #    killnum = len(self.workers) - self.opts.num_workers
                #    for w in self.workers[:killnum]:
                # insert a poison pill? Kill after something? I dunno.
                # FIXME - if a worker bombs out - we need to check them
                # and startup a new one if it happens
                # check for dead workers and abort
                preserved_workers = self.prune_dead_workers_by_group_id(group_id)
                self.workers_by_group_id[group_id] = preserved_workers

            time.sleep(self.opts.sleeptime)


def run_backend(opts):
    """
    Start main backend daemon

    :param opts: Bunch object with command line options

    Expected **opts** fields:
        - `config_file` - path to the backend config file
        - `daemonize` - boolean flag to enable daemon mode
        - `pidfile` - path to the backend pidfile

    """
    cbe = None
    try:
        context = DaemonContext(
            pidfile=lockfile.FileLock(opts.pidfile),
            gid=grp.getgrnam("copr").gr_gid,
            uid=pwd.getpwnam("copr").pw_uid,
            detach_process=opts.daemonize,
            umask=0o22,
            stderr=sys.stderr,
            signal_map={
                signal.SIGTERM: "terminate",
                signal.SIGHUP: "terminate",
            },
        )
        with context:
            cbe = CoprBackend(opts.config_file, ext_opts=opts)
            cbe.run()
    except (Exception, KeyboardInterrupt):
        sys.stderr.write("Killing/Dying\n")
        if cbe is not None:
            cbe.terminate()
        raise
