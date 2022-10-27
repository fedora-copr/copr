from copr_common.worker_manager import QueueTask


class BackendQueueTask(QueueTask):
    """
    A base class for tasks processed by `BackendDispatcher` implementations
    """
    # pylint: disable=abstract-method

    @property
    def priority(self):
        return sum([self.frontend_priority, self.backend_priority])

    @property
    def frontend_priority(self):
        """
        A task priority is calculated based on a frontend priority preference
        and backend priority preference.

        This is the frontend priority number
        """
        return 0

    @property
    def backend_priority(self):
        """
        A task priority is calculated based on a frontend priority preference
        and backend priority preference.

        This is the backend priority number
        """
        return 0
