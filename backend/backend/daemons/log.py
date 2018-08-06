# coding: utf-8

import json

import logging
import logging.handlers
import os
from setproctitle import setproctitle


# TODO: remove when RedisLogHandler works fine
from .. import constants
from .. import helpers
from ..constants import default_log_format


level_map = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "error": logging.ERROR,
}


class LogRouterFilter(logging.Filter):
    def __init__(self, who):
        """
        Value of field `who` which should be present to propagate LogRecord
        """
        super(LogRouterFilter, self).__init__()
        self.who = who

    def filter(self, record):
        return record.event.get("who") == self.who


class CustomFilter(logging.Filter):

    def filter(self, record):
        if not hasattr(record, "event"):
            return False

        event = record.event
        if "traceback" in event:
            record.msg = "{}\n{}".format(record.msg, event.pop("traceback"))

        record.lineno = int(event.pop("lineno", "-1"))
        record.funcName = event.pop("funcName", None)
        record.pathname = event.pop("pathname", None)
        for k, v in event.items():
            setattr(record, k, v)

        return True


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

        self.components = ["spawner", "terminator", "vmm", "build_dispatcher",
                           "action_dispatcher", "backend", "actions", "worker"]

    def setup_logging(self):

        self.main_logger = logging.Logger("logger", level=logging.DEBUG)
        self.main_handler = logging.handlers.WatchedFileHandler(
            filename=os.path.join(self.log_dir, "logger.log"))
        self.main_handler.setFormatter(default_log_format)
        self.main_logger.addHandler(self.main_handler)

        self.router_logger = logging.Logger("log_router")
        self.router_logger.addFilter(CustomFilter())

        for component in self.components:
            handler = logging.handlers.WatchedFileHandler(
                filename=os.path.join(self.log_dir, "{}.log".format(component)))
            handler.setFormatter(default_log_format)
            handler.setLevel(level=level_map[self.opts.log_level])
            # not very good from performance point:
            #   filter called for each message, but only one handler process record
            # but it shouldn't be a real problem
            handler.addFilter(filter=LogRouterFilter(component))
            self.router_logger.addHandler(handler)

    def handle_msg(self, raw):
        try:
            event = json.loads(raw["data"])

            # expected fields:
            #   - who: self.components
            #   - level: "info", "debug", "error", None --> default is "info"
            #   - msg: str with log msg
            #   [- traceback: str with error traceback ]
            #   [ more LogRecord kwargs, see: https://docs.python.org/2/library/logging.html#logrecord-objects]

            for key in ["who", "msg"]:
                if key not in event:
                    raise Exception("Handler received msg without `{}` field, msg: {}".format(key, event))

            who = event["who"]
            if who not in self.components:
                raise Exception("Handler received msg with unknown `who` field: {}, msg: {}".format(who, event))

            level = level_map[event.pop("level", "info")]
            msg = event.pop("msg")

            self.router_logger.log(level, msg, extra={"event": event})

        except Exception as err:
            self.main_logger.exception(err)

    def run(self):
        self.setup_logging()
        setproctitle("RedisLogHandler")

        rc = helpers.get_redis_connection(self.opts)
        channel = rc.pubsub(ignore_subscribe_messages=True)
        channel.subscribe(constants.LOG_PUB_SUB)

        for raw in channel.listen():
            if raw is not None and raw.get("type") == "message" and "data" in raw:
                self.handle_msg(raw)
