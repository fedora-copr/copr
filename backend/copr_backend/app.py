"""
The Copr project globals to simplify access to config, logging, etc.
"""

import logging
import os
from copr_backend.helpers import (
    BackendConfigReader,
    get_redis_log_handler,
    RedisPublishHandler,
)


class App:
    """
    Shortcut.
    """
    log = None

    def __init__(self):
        self._setup_logging()
        self.config_file = os.environ.get("BACKEND_CONFIG",
                                          "/etc/copr/copr-be.conf")
        self.opts = BackendConfigReader(self.config_file).read()

    def _setup_logging(self):
        logging.basicConfig(level=logging.DEBUG)
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)

    def setup_redis_logging(self, filename):
        """
        Setup a multiprocessing logger to a file inside /var/log/copr-backend,
        using the Redis handler.
        """
        for handler in self.log.handlers:
            if isinstance(handler, RedisPublishHandler):
                return
        self.log.addHandler(get_redis_log_handler(self.opts, filename))

    def redirect_to_redis_log(self, filename):
        """
        Drop all handlers from self.log, and add one going through Redis
        """
        self.log.handlers = []
        self.setup_redis_logging(filename)
