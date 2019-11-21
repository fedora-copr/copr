# coding: utf-8

import time
import multiprocessing

from collections import defaultdict

from setproctitle import setproctitle

from backend.frontend import FrontendClient

from ..helpers import get_redis_logger
from ..exceptions import (DispatchBuildError, NoVmAvailable,
                          FrontendClientException)
from ..job import BuildJob
from ..vm_manage.manager import VmManager
from ..constants import BuildStatus
from .worker import Worker


class BuildDispatcher(multiprocessing.Process):
    """
    1) Fetch build tasks from frontend
    2) Loop through them and try to allocate VM for each
       - If VM can be allocated, spawn a worker and run it asynchronously
       - otherwise, check the next build task
    3) Go to 1
    """

    def __init__(self, opts):
        multiprocessing.Process.__init__(self, name="build-dispatcher")

        self.opts = opts
        self.log = get_redis_logger(self.opts, "backend.build_dispatcher", "build_dispatcher")
        self.frontend_client = FrontendClient(self.opts, self.log)
        self.vm_manager = VmManager(self.opts)
        self.workers = []
        self.next_worker_id = 1

        self.arch_to_groups = defaultdict(list)
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

            for arch in group["archs"]:
                self.arch_to_groups[arch].append(group_id)
                self.log.debug("mapping %s to %s group", arch, group_id)

            self.log.debug("user might use only %sVMs for %s group", group["max_vm_per_user"], group_id)
            self.group_to_usermax[group_id] = group["max_vm_per_user"]

    def load_jobs(self):
        """
        Retrieve a single build job from frontend.
        """
        self.log.info("Waiting for a job from frontend...")
        get_task_init_time = time.time()
        tasks = None

        while not tasks:
            self.update_process_title("Waiting for jobs from frontend for {} s"
                                      .format(int(time.time() - get_task_init_time)))
            try:
                tasks = self.frontend_client.get('pending-jobs').json()
            except (FrontendClientException, ValueError) as error:
                self.log.exception("Retrieving build jobs from %s failed with error: %s",
                                   self.opts.frontend_base_url, error)
            finally:
                if not tasks:
                    time.sleep(self.opts.sleeptime)

        self.log.info("Got new build jobs: %s", [task.get("task_id") for task in tasks if task])
        return [BuildJob(task, self.opts) for task in tasks if task]

    def can_build_start(self, job):
        """
        Announce to the frontend that the build is starting. Frontend
        may reject build to start.

        Returns
        -------
        True if the build can start
        False if the build can not start (build is cancelled)
        """
        try:
            job.started_on = time.time()
            job.status = BuildStatus.STARTING
            can_build_start = self.frontend_client.starting_build(job.to_dict())
        except (FrontendClientException, ValueError) as error:
            self.log.exception("Communication with Frontend to confirm build start failed with error: %s", error)
            return False

        if not can_build_start:
            self.log.exception("Frontend forbade to start the job %s", job.task_id)

        return can_build_start

    def clean_finished_workers(self):
        for worker in self.workers:
            if not worker.is_alive():
                worker.join(5)
                self.workers.remove(worker)
                self.log.info("Removed finished worker %s for job %s",
                              worker.worker_id, worker.job.task_id)

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

        first_backend_loop = True

        while True:
            self.clean_finished_workers()

            skip_jobs_cache = {}

            for job in self.load_jobs():
                # first check if we do not have
                # worker already running for the job
                if any([job.task_id == w.job.task_id for w in self.workers]):
                    self.log.debug("Skipping already running task '%s'",
                                   job.task_id)
                    continue

                if first_backend_loop:
                    # Server was restarted.  Some builds might be running on
                    # background on builders;  so search db builder records for
                    # the job and if we found it, spawn a worker to reattach.
                    vm = self.vm_manager.get_vm_by_task_id(job.task_id)
                    if vm and vm.state == 'in_use':
                        self.log.info("Reattaching to VM: "+str(vm))
                        worker = self.start_worker(vm, job, reattach=True)
                        vm.store_field(self.vm_manager.rc, "used_by_worker", worker.worker_id)
                        self.log.info("Reattached new worker %s for job %s",
                                      worker.worker_id, worker.job.task_id)
                        continue

                cache_entry = '{owner}-{arch}-{sandbox}'.format(
                    owner=job.project_owner,
                    arch=job.arch or "noarch",
                    sandbox=job.sandbox,
                )

                if cache_entry in skip_jobs_cache:
                    self.log.debug("Skipped job %s, cached", job)
                    continue

                # ... and if the task is new to us,
                # allocate new vm and run full build
                try:
                    vm_group_ids = self.get_vm_group_ids(job.arch)
                    self.log.debug("Picking VM from groups %s for job %s", vm_group_ids, job)
                    vm = self.vm_manager.acquire_vm(
                        vm_group_ids, job.project_owner, job.sandbox,
                        self.next_worker_id, job.task_id, job.build_id,
                        job.chroot)
                except NoVmAvailable as error:
                    skip_jobs_cache[cache_entry] = True
                    self.log.debug("No available resources for task %s (Reason: %s). Deferring job.",
                                   job.task_id, error)
                    continue
                else:
                    self.log.info("VM %s for job %s successfully acquired", vm.vm_name, job.task_id)

                if not self.can_build_start(job):
                    self.vm_manager.release_vm(vm.vm_name)
                    continue

                worker = self.start_worker(vm, job)
                self.log.info("Started new worker %s for job %s",
                              worker.worker_id, worker.job.task_id)

            first_backend_loop = False
            time.sleep(self.opts.sleeptime)
