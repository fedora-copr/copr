"""
BuildDispatcher related classes.
"""

from copr_backend.dispatcher import Dispatcher
from copr_backend.rpm_builds import RPMBuildWorkerManager, BuildQueueTask

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
