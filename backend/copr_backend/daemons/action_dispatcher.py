"""
ActionDispatcher related classes.
"""

from copr_backend.exceptions import FrontendClientException
from copr_backend.dispatcher import BackendDispatcher
from copr_backend.rpm_builds import BlockedOwnersLimit

from ..actions import ActionWorkerManager, ActionQueueTask, Action

class ActionDispatcher(BackendDispatcher):
    """
    Kick-off action dispatcher daemon.
    """
    task_type = 'action'
    worker_manager_class = ActionWorkerManager

    def __init__(self, backend_opts):
        super().__init__(backend_opts)
        self.max_workers = backend_opts.actions_max_workers

        blocked_owners = backend_opts.builds_limits["blocked_owners"]
        self.limits.append(BlockedOwnersLimit(blocked_owners))
        self.log.info("setting limit for blocked owners: %s", blocked_owners)

    def get_frontend_tasks(self):
        try:
            raw_actions = self.frontend_client.get('pending-actions').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception(
                "Retrieving an action tasks failed with error: %s",
                error)
            return []

        return [ActionQueueTask(Action(self.opts, action, log=self.log))
                for action in raw_actions]
