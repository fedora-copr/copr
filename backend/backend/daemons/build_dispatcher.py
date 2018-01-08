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

from collections import defaultdict

class BuildDispatcher(multiprocessing.Process):
    """
    1) Fetch build task from frontend
    2) Get an available VM for it
    3) Create a worker for the job
    4) Start worker asynchronously and go to 1)
    """

    def __init__(self, opts):
        multiprocessing.Process.__init__(self, name="build-dispatcher")

        self.opts = opts
        self.log = get_redis_logger(self.opts, "backend.build_dispatcher", "build_dispatcher")
        self.frontend_client = FrontendClient(self.opts, self.log)
        self.vm_manager = VmManager(self.opts)
        self.workers = []
        self.next_worker_id = 1

        self.all_archs = set()
        self.arch_to_groups = defaultdict(list)
        self.group_to_archs = dict()
        # PC => max N builders per user
        self.group_to_usermax = dict()

        self.init_internal_structures()

    def get_vm_group_ids(self, arch):
        if not arch:
            return [group["id"] for group in self.opts.build_groups]

        try:
            return self.arch_to_groups[arch]
        except KeyError:
            raise DispatchBuildError("Unknown architecture {0}".format(arch))

    def update_process_title(self, msg=None):
        proc_title = "Build dispatcher"
        if msg:
            proc_title += " - " + msg
        setproctitle(proc_title)

    def init_internal_structures(self):
        for group in self.opts.build_groups:
            group_id = group["id"]
            self.group_to_archs[group_id] = group["archs"]
            self.all_archs |= set(group["archs"])

            for arch in group["archs"]:
                self.arch_to_groups[arch].append(group_id)
                self.log.debug("mapping {0} to {1} group".format(arch, group_id))

            self.log.debug("user might use only {0}VMs for {1} group".format(group["max_vm_per_user"], group_id))
            self.group_to_usermax[group_id] = group["max_vm_per_user"]

    def get_job_select_params(self):
        """
        Construct job selection criteria for copr-frontend.
        """
        missing_worker_task_ids = []
        worker_ids = self.get_worker_ids()
        for vm in self.vm_manager.get_all_vm():
            if vm.used_by_worker and int(vm.used_by_worker) not in worker_ids:
                missing_worker_task_ids.append(vm.task_id)

        available_archs = set()
        available_archs_per_job_owner = defaultdict(set)

        for group in self.opts.build_groups:
            group_id = group["id"]
            ready_vms = self.vm_manager.get_ready_vms(group_id)

            if ready_vms:
                available_archs |= set(self.group_to_archs[group_id])

            for dirty_vm in self.vm_manager.get_dirty_vms(group_id):
                available_archs_per_job_owner[dirty_vm.bound_to_user] |= set()

            for owner in available_archs_per_job_owner:
                ready_dirtied_by_owner = [vm for vm in ready_vms if vm.bound_to_user == owner]
                owner_can_acquire_more = self.vm_manager.can_user_acquire_more_vm(owner, group_id)
                if ready_vms and (owner_can_acquire_more or ready_dirtied_by_owner):
                    archs_to_add = self.group_to_archs[group_id]
                    available_archs_per_job_owner[owner] |= set(archs_to_add)

        exclude_owners = []
        exclude_owner_arch_pairs = set()
        for owner, archs in available_archs_per_job_owner.items():
            if not archs:
                exclude_owners.append(owner)

            excluded_archs = self.all_archs - archs
            for arch in excluded_archs:
                exclude_owner_arch_pairs.add((owner, arch))

        return {
            'provide_task_ids': missing_worker_task_ids,
            'exclude_archs': self.all_archs - available_archs,
            'exclude_owners': exclude_owners,
            'exclude_owner_arch_pairs': exclude_owner_arch_pairs,
        }

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
                job_select_params = self.get_job_select_params()

                if not job_select_params.get("provide_task_ids") and \
                        self.all_archs == job_select_params.get("exclude_archs"):
                    self.log.info("No arch is available for building. Going to sleep...")
                    time.sleep(self.opts.sleeptime)
                    continue

                exclude_owner_arch_pairs_encoded = []
                for pair in job_select_params["exclude_owner_arch_pairs"]:
                    exclude_owner_arch_pairs_encoded.append(pair[0]+","+pair[1])
                job_select_params["exclude_owner_arch_pairs"] = exclude_owner_arch_pairs_encoded

                task = get("{0}/backend/select-build-task/".format(self.opts.frontend_base_url),
                           auth=("user", self.opts.frontend_auth), params=job_select_params).json()

            except (RequestException, ValueError) as error:
                self.log.exception("Retrieving build job from {} failed with error: {}"
                                   .format(self.opts.frontend_base_url, error))
            finally:
                if not task:
                    time.sleep(self.opts.sleeptime)

        self.log.info("Got new build job {}".format(task.get("task_id")))
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

    def get_worker_ids(self):
        return [worker.worker_id for worker in self.workers]

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
                self.log.info("Reattaching to VM: "+str(vm))
                worker = self.start_worker(vm, job, reattach=True)
                worker.mark_started(job)
                vm.store_field(self.vm_manager.rc, "used_by_worker", worker.worker_id)
                self.log.info("Reattached new worker {} for job {}"
                              .format(worker.worker_id, worker.job.task_id))
                continue

            # ... and if the task is new to us,
            # allocate new vm and run full build
            try:
                self.log.info("Acquiring VM for job {}...".format(job))
                vm_group_ids = self.get_vm_group_ids(job.arch)
                self.log.info("Picking VM from groups {}".format(vm_group_ids))
                vm = self.vm_manager.acquire_vm(vm_group_ids, job.project_owner, self.next_worker_id,
                                                job.task_id, job.build_id, job.chroot)
            except NoVmAvailable as error:
                self.log.info("No available resources for task {} (Reason: {}). Deferring job."
                              .format(job.task_id, error))
                self.frontend_client.defer_build(job.build_id, job.chroot)
                time.sleep(self.opts.sleeptime)
                continue
            else:
                self.log.info("VM {} for job {} successfully acquired".format(vm.vm_name, job.task_id))

            if not self.can_build_start(job):
                self.vm_manager.release_vm(vm.vm_name)
                time.sleep(self.opts.sleeptime)
                continue

            worker = self.start_worker(vm, job)
            self.log.info("Started new worker {} for job {}"
                          .format(worker.worker_id, worker.job.task_id))
