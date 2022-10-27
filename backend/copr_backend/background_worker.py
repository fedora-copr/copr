"""
Helper methods/classes for 'copr-backend-*' scripts.
"""

import os
import sys
import logging

from copr_common.background_worker import BackgroundWorker
from copr_backend.frontend import FrontendClient
from copr_backend.helpers import (BackendConfigReader, get_redis_logger)


class BackendBackgroundWorker(BackgroundWorker):
    """
    copr-backend-process-* abstraction
    """

    # This is still a base class, abstract methods will be overriden
    # in its descendants
    # pylint: disable=abstract-method

    def __init__(self):
        super().__init__()

        be_cfg = self.args.backend_config or '/etc/copr/copr-be.conf'
        self.opts = BackendConfigReader(be_cfg).read()

        self.frontend_client = FrontendClient(self.opts, self.log,
                                              try_indefinitely=True)

    def _switch_logger_to_redis(self):
        if not self.has_wm:
            return

        logger_name = '{}.{}.pid-{}'.format(
            sys.argv[0],
            'managed' if self.args.worker_id else 'manual',
            os.getpid(),
        )

        self.log = get_redis_logger(self.opts, logger_name,
                                    self.redis_logger_id)
        if not self.args.daemon and not self.args.silent:
            # when executing from commandline - on foreground - we want to
            # print something to stderr as well
            self.log.addHandler(logging.StreamHandler())

    def _daemonized_part(self):
        # notify WorkerManager first, to minimize race window
        self._wm_started()

        # setup logging early, to have as complete logs as possible
        self._switch_logger_to_redis()

        super()._daemonized_part()
