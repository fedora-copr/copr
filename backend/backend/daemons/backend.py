# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import grp
import pwd
import signal
import sys
import time
from collections import defaultdict

import lockfile
from daemon import DaemonContext
from requests import RequestException
from retask import ConnectionError
from backend.frontend import FrontendClient

from ..exceptions import CoprBackendError
from ..helpers import BackendConfigReader, get_redis_logger
from .dispatcher import Worker
from .. import jobgrabcontrol


class CoprBackend(object):

    """
    Core process - starts/stops/initializes workers


    :param config_file: path to the backend configuration file
    :param ext_opts: additional options for backend
    """

    def __init__(self, config_file=None, ext_opts=None):
        # read in config file
        # put all the config items into a single self.opts munch

        if not config_file:
            raise CoprBackendError("Must specify config_file")

        self.config_file = config_file
        self.ext_opts = ext_opts  # to show our cli options for read_conf()
        self.workers_by_group_id = defaultdict(list)
        self.max_worker_num_by_group_id = defaultdict(int)

        self.config_reader = BackendConfigReader(self.config_file, self.ext_opts)
        self.opts = None
        self.update_conf()

        self.task_queues = {}

        self.log = get_redis_logger(self.opts, "backend.main", "backend")

        self.frontend_client = FrontendClient(self.opts, self.log)
        self.jg_control = jobgrabcontrol.Channel(self.opts, self.log)
        self.is_running = False

    def init_task_queues(self):
        """
        Remove old tasks from queues.
        """
        self.jg_control.backend_start()

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
            self.log.info("Spinning up more workers")
            for _ in range(group["max_workers"] - len(self.workers_by_group_id[group_id])):
                self.max_worker_num_by_group_id[group_id] += 1
                try:
                    w = Worker(
                        opts=self.opts,
                        frontend_client=self.frontend_client,
                        worker_num=self.max_worker_num_by_group_id[group_id],
                        group_id=group_id
                    )

                    self.workers_by_group_id[group_id].append(w)
                    w.start()
                    time.sleep(0.3)
                    self.log.info("Started worker: {} for group: {}".format(w.worker_num, group_id))
                except Exception as error:
                    self.log.exception("Failed to start new Worker: {}".format(error))

            self.log.info("Finished starting worker processes")

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
                self.log.warn("Worker {} died unexpectedly".format(w.worker_num))
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

        self.is_running = False
        for group in self.opts.build_groups:
            group_id = group["id"]
            for w in self.workers_by_group_id[group_id][:]:
                self.workers_by_group_id[group_id].remove(w)
                w.terminate_instance()

        try:
            self.log.info("Rescheduling unfinished builds before stop")
            self.frontend_client.reschedule_all_running(5)
        except RequestException as err:
            self.log.exception(err)
            return

    def run(self):
        """
        Starts backend process. Control sub process start/stop.
        """
        self.update_conf()
        self.init_task_queues()
        time.sleep(1)
        self.log.info("Initial config: {}".format(self.opts))

        try:
            self.log.info("Rescheduling old unfinished builds")
            # 120*5 = 10 minutes
            self.frontend_client.reschedule_all_running(120)
        except RequestException as err:
            self.log.exception(err)
            return

        self.is_running = True
        while self.is_running:
            # re-read config into opts
            self.update_conf()

            for group in self.opts.build_groups:
                group_id = group["id"]

                self.spin_up_workers_by_group(group)
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

    :param opts: Munch object with command line options

    Expected **opts** fields:
        - `config_file` - path to the backend config file
        - `daemonize` - boolean flag to enable daemon mode
        - `pidfile` - path to the backend pidfile

        - `daemon_user`
        - `daemon_group`
    """
    cbe = None
    try:
        context = DaemonContext(
            pidfile=lockfile.FileLock(opts.pidfile),
            # gid=grp.getgrnam("copr").gr_gid,
            # uid=pwd.getpwnam("copr").pw_uid,
            gid=grp.getgrnam(opts.daemon_user).gr_gid,
            uid=pwd.getpwnam(opts.daemon_group).pw_uid,
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
