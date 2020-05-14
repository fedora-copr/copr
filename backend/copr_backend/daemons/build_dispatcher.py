"""
BuildDispatcher related classes.
"""

from copr_backend.dispatcher import Dispatcher
from copr_backend.rpm_builds import (
    ArchitectureWorkerLimit,
    RPMBuildWorkerManager,
    BuildQueueTask,
)
from copr_backend.worker_manager import GroupWorkerLimit
from ..exceptions import FrontendClientException


class BuildDispatcher(Dispatcher):
    """
    Kick-off build dispatcher daemon.
    """
    task_type = 'build'
    worker_manager_class = RPMBuildWorkerManager

    def __init__(self, backend_opts):
        super().__init__(backend_opts)
        self.max_workers = backend_opts.builds_max_workers
        for arch, limit  in backend_opts.builds_limits['arch'].items():
            self.log.info("setting %s limit to %s", arch, limit)
            self.limits.append(ArchitectureWorkerLimit(arch, limit))
        for limit_type in ['sandbox', 'owner']:
            max_builders = backend_opts.builds_limits[limit_type]
            self.log.info("setting %s limit to %s", limit_type, max_builders)
            self.limits.append(GroupWorkerLimit(
                lambda x, limit=limit_type: getattr(x, limit),
                max_builders,
                name=limit_type,
            ))

    def get_frontend_tasks(self):
        """
        Retrieve a list of build jobs to be done.
        """
        try:
            raw_tasks = self.frontend_client.get('pending-jobs').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception("Retrieving build jobs from %s failed with error: %s",
                               self.opts.frontend_base_url, error)
            return []

        tasks = []
        for raw in raw_tasks:
            task = BuildQueueTask(raw)
            tasks.append(task)
        return tasks

    def get_cancel_requests_ids(self):
        try:
            return self.frontend_client.get('build-tasks/cancel-requests').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception("Retrieving build jobs from %s failed with error: %s",
                               self.opts.frontend_base_url, error)
            return []

    def canceled_task_id(self, task_id):
        self.frontend_client.post('build-tasks/canceled/{}'.format(task_id), None)
