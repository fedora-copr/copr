# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import time
import os
import multiprocessing
import json
from setproctitle import setproctitle
from requests import get, RequestException

from backend.frontend import FrontendClient

from ..helpers import get_redis_logger
from ..exceptions import DispatchBuildError, NoVmAvailable
from ..job import BuildJob
from ..vm_manage.manager import VmManager
from .worker import Worker


class BuildDispatcher(multiprocessing.Process):
    """
    1) Fetch build task from frontend
    2) Get a free VM for it
    3) Create a worker for the job
    4) Start it asynchronously and go to 1)
    """

    def __init__(self, opts):
        multiprocessing.Process.__init__(self, name="build-dispatcher")

        self.opts = opts
        self.log = get_redis_logger(self.opts, "backend.build_dispatcher", "build_dispatcher")
        self.frontend_client = FrontendClient(self.opts, self.log)
        self.vm_manager = VmManager(self.opts)
        self.workers = []
        self.next_worker_id = 1

        # Maps e.g. x86_64 && i386 => PC
        self.arch_to_group = dict()
        # PC => max N builders per user
        self.group_to_usermax = dict()

        self.init_internal_structures()

    def get_vm_group_id(self, arch):
        try:
            return self.arch_to_group[arch]
        except KeyError:
            raise DispatchBuildError("Unknown architecture {0}".format(arch))

    def update_process_title(self, msg=None):
        proc_title = "Build dispatcher"
        if msg:
            proc_title += " - " + msg
        setproctitle(proc_title)

    def init_internal_structures(self):
           self.arch_to_group = dict()
           self.group_to_usermax = dict()
           for group in self.opts.build_groups:
               group_id = group["id"]
               for arch in group["archs"]:
                   self.arch_to_group[arch] = group_id
                   self.log.debug("mapping {0} to {1} group".format(arch, group_id))

               self.log.debug("user might use only {0}VMs for {1} group".format(group["max_vm_per_user"], group_id))
               self.group_to_usermax[group_id] = group["max_vm_per_user"]

    def load_job(self):
        """
        Retrieve a single build job from frontend.
        """
        self.log.info("Waiting for a job from frontend...")
        get_task_init_time = time.time()

        task = None
        while not task:
            self.update_process_title("Waiting for a job from frontend for {} s"
                                      .format(int(time.time() - get_task_init_time)))
            try:
                r = get("{0}/backend/waiting/".format(self.opts.frontend_base_url),
                        auth=("user", self.opts.frontend_auth))
                task = r.json().get("build")
            except (RequestException, ValueError) as error:
                self.log.exception("Retrieving build job from {} failed with error: {}"
                                   .format(self.opts.frontend_base_url, error))
            finally:
                if not task:
                    time.sleep(self.opts.sleeptime)

        self.log.info("Got new build job {}".format(task['task_id']))
        return BuildJob(task, self.opts)

    def can_build_start(self, job):
        """
        Announce to the frontend that the build is going to start so that
        it can confirm that and draw out another job for building.

        Returns
        -------
        True if the build can start
        False if the build can not start (build is cancelled)
        """
        try:
            can_build_start = self.frontend_client.starting_build(job.build_id, job.chroot)
        except (RequestException, ValueError) as error:
            self.log.exception("Communication with Frontend to confirm build start failed with error: {}".format(error))
            return False

        if not can_build_start:
            self.log.exception("Frontend forbade to start the job {}".format(job.task_id))

        return can_build_start

    def clean_finished_workers(self):
        for worker in self.workers:
            if not worker.is_alive():
                worker.join(5)
                self.workers.remove(worker)
                self.log.info("Removed finished worker {} for job {}"
                              .format(worker.worker_id, worker.job.task_id))

    def start_worker(self, vm, job, reattach=False):
        worker = Worker(
            opts=self.opts,
            frontend_client=self.frontend_client,
            vm_manager=self.vm_manager,
            worker_id=self.next_worker_id,
            vm=vm, job=job, reattach=reattach
        )
        self.workers.append(worker)
        self.next_worker_id = (self.next_worker_id + 1) % 2**15

        worker.start()
        return worker

    def run(self):
        """
        Executes build dispatching process.
        """
        self.log.info("Build dispatching started.")
        self.update_process_title()

        while True:
            self.clean_finished_workers()

            job = self.load_job()

            # now search db builder records for the job and
            # if we found it, just spawn a worker to reattach
            vm = self.vm_manager.get_vm_by_task_id(job.task_id)
            if vm and vm.state == 'in_use':
                worker = self.start_worker(vm, job, reattach=True)
                worker.mark_started(job)
                vm.store_field(self.vm_manager.rc, "used_by_pid", os.getpid())
                self.log.info("Reattached new worker {} for job {}"
                              .format(worker.worker_id, worker.job.task_id))
                continue

            # ... and if the task is new to us,
            # allocate new vm and run full build
            try:
                self.log.info("Acquiring VM for job {}...".format(str(job)))
                vm_group_id = self.get_vm_group_id(job.arch)
                vm = self.vm_manager.acquire_vm(vm_group_id, job.project_owner, os.getpid(),
                                                job.task_id, job.build_id, job.chroot)
            except NoVmAvailable as error:
                self.log.info("No available resources for task {} (Reason: {}). Deferring job."
                              .format(job.task_id, error))
                self.frontend_client.defer_build(job.build_id, job.chroot)
                continue
            else:
                self.log.info("VM {} for job {} successfully acquired".format(vm.vm_name, job.task_id))

            if not self.can_build_start(job):
                self.vm_manager.release_vm(vm.vm_name)
                continue

            worker = self.start_worker(vm, job)
            self.log.info("Started new worker {} for job {}"
                          .format(worker.worker_id, worker.job.task_id))
