# coding: utf-8

import json

import logging
import logging.handlers
import os
from setproctitle import setproctitle

from copr_common.redis_helpers import get_redis_connection

# TODO: remove when RedisLogHandler works fine
from .. import constants
from .. import helpers


class RedisLogHandler(object):
    """
    Single point to collect logs through redis pub/sub and write
        them through standard python logging lib
    """

    def __init__(self, opts):
        self.opts = opts

        self.log_dir = os.path.dirname(self.opts.log_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, mode=0o750)
        self.components = helpers.LOG_COMPONENTS

    def setup_logging(self):

        self.main_logger = logging.Logger("logger", level=logging.DEBUG)
        self.main_handler = logging.handlers.WatchedFileHandler(
            filename=os.path.join(self.log_dir, "logger.log"))
        self.main_handler.setFormatter(self.opts.log_format)
        self.main_logger.addHandler(self.main_handler)

        level = getattr(logging, self.opts.log_level.upper(), None)
        self.loggers = {}

        for component in self.components:
            logger = logging.Logger(component)
            handler = logging.handlers.WatchedFileHandler(
                filename=os.path.join(self.log_dir, "{}.log".format(component)))
            handler.setFormatter(self.opts.log_format)
            handler.setLevel(level)
            logger.addHandler(handler)
            self.loggers[component] = logger

    def handle_msg(self, json_event):
        try:
            event = json.loads(json_event)
            who = event.get('who', None)
            if not who:
                raise Exception("No LogRecord.who field, raw: {}".format(event))
            if who not in self.loggers:
                raise Exception("Unknown LogRecord.who field: {}, raw event: {}"
                                .format(who, event))

            log_record = logging.makeLogRecord(event)
            self.loggers[who].handle(log_record)

        except Exception as err:
            self.main_logger.exception(err)

    def run(self):
        self.setup_logging()
        setproctitle("RedisLogHandler")

        rc = get_redis_connection(self.opts)
        while True:
            # indefinitely wait for the next entry, note that blpop returns
            # tuple (FIFO_NAME, ELEMENT)
            (_, json_event) = rc.blpop([constants.LOG_REDIS_FIFO])
            self.handle_msg(json_event)
