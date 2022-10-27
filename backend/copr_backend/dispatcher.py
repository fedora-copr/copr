"""
Abstract class Dispatcher for Build/Action dispatchers.
"""

from copr_common.dispatcher import Dispatcher
from copr_backend.frontend import FrontendClient
from copr_backend.helpers import get_redis_logger


class BackendDispatcher(Dispatcher):
    """
    Base class for backend dispatchers
    """

    # This is still a base class, abstract methods will be overriden
    # in its descendants
    # pylint: disable=abstract-method

    def __init__(self, opts):
        super().__init__(opts)

        logger_name = 'backend.{}_dispatcher'.format(self.task_type)
        logger_redis_who = '{}_dispatcher'.format(self.task_type)
        self.log = get_redis_logger(self.opts, logger_name, logger_redis_who)

        self.frontend_client = FrontendClient(self.opts, self.log)
        self.sleeptime = opts.sleeptime
