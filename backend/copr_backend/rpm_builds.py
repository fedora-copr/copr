"""
Abstraction for RPM and SRPM builds on backend.
"""

import subprocess

from copr_backend.helpers import get_chroot_arch
from copr_backend.worker_manager import (
    PredicateWorkerLimit,
    QueueTask,
    WorkerManager,
)

class BuildQueueTask(QueueTask):
    """
    Build-task abstraction.  Needed for build our build scheduler (the
    WorkerManager class).

    Note that the worker counterpart (BackgroundWorker process) needs by far
    more information about the job to successfully process it.  But since we
    need to minimize the amount of informations downloaded by
    BuildDispatcher.load_jobs() method from frontent (performance reasons) we
    keep this in separate class.
    """
    def __init__(self, task):
        self._task = task

    @property
    def frontend_priority(self):
        return self._task.get('priority', 0)

    @property
    def id(self):
        return self._task['task_id']

    @property
    def build_id(self):
        """ Copr Frontend build.id this relates to. """
        return self._task['build_id']

    @property
    def chroot(self):
        """
        The chroot this task will be built in.  We return 'source' if this is
        source RPM build - in such case the build should be arch agnostic.
        """
        task_chroot = self._task.get('chroot')
        if not task_chroot:
            task_chroot = 'srpm-builds'
        return task_chroot

    @property
    def owner(self):
        """ Owner of the project this build belongs to """
        return self._task["project_owner"]

    @property
    def requested_arch(self):
        """
        What is the requested "native" builder architecture for which this
        build task will be done.  We use this for limiting the build queue
        (i.e. separate limit for armhfp, even though such build process is
        emulated on x86_64).
        """
        if self.chroot == "srpm-builds":
            return None
        arch = get_chroot_arch(self.chroot)
        if arch.endswith("86"):
            # i386, i586, ...
            return "x86_64"
        return arch

    @property
    def sandbox(self):
        """
        Unique ID of "sandbox" to put the VM worker into.  Multiple builds can
        fall into the same sandbox, but only when it is absolutely safe (the
        same submitter, the same project, etc.).

        Frontend doesn't necessarily have to specify sandbox for each build,
        then we return None.  The consequence is that the allocated VM to such
        task is not possible to re-use for other purposes (before or after this
        task is processed).
        """
        return self._task.get('sandbox')


class ArchitectureWorkerLimit(PredicateWorkerLimit):
    """
    Limit the amount of concurrently running builds for the same architecture.
    """
    def __init__(self, architecture, limit):
        def predicate(x):
            return x.requested_arch == architecture
        super().__init__(predicate, limit, name="arch_{}".format(architecture))


class RPMBuildWorkerManager(WorkerManager):
    """
    Manager taking care of background build workers.
    """

    worker_prefix = 'rpm_build_worker'

    def start_task(self, worker_id, task):
        command = [
            "copr-backend-process-build",
            "--daemon",
            "--build-id", str(task.build_id),
            "--chroot", task.chroot,
            "--worker-id", worker_id,
        ]
        self.log.info("running worker: %s", " ".join(command))
        subprocess.check_call(command)

    def finish_task(self, worker_id, task_info):
        self.get_task_id_from_worker_id(worker_id)
        return True
