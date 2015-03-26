# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import json

import logging
import logging.handlers
from multiprocessing import Process
import os
import sys
import time
from setproctitle import setproctitle


# TODO: remove when RedisLogHandler works fine
from .. import constants
from .. import helpers
from ..constants import default_log_format


class CoprBackendLog(Process):

    """Log mechanism where items from the events queue get recorded

    :param Bunch opts: backend config
    :param events: multiprocessing.Queue to listen
        for events from other backend components

    """

    def __init__(self, opts, events):

        # base class initialization
        Process.__init__(self, name="logger")

        self.opts = opts
        self.events = events

        logdir = os.path.dirname(self.opts.logfile)
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0o750)

    def setup_log_handler(self):
        """
        Configures standard python logger
        """
        sys.stderr.write("Running setup handler {} \n".format(self.opts))
        # setup a log file to write to
        logging.basicConfig(filename=self.opts.logfile + "_old.log", level=logging.DEBUG)

        self.log({"when": time.time(), "who": self.__class__.__name__,
                  "what": "Logger initiated"})

    def log(self, event):
        """
        Format event into the log message

        :param event: dict-like object

        Expected **event** keys:
            - `when`: unixtime
            - `who`: event producer [worker|logger|job|main]
            - `what`: content
        """
        when = time.strftime("%F %T", time.gmtime(event["when"]))
        msg = "{0} : {1}: {2}".format(when,
                                      event["who"],
                                      event["what"].strip())
        try:
            if self.opts.verbose:
                sys.stderr.write("{0}\n".format(msg))
                sys.stderr.flush()
            # logging.debug(msg)

        except (IOError, OSError) as e:

            sys.stderr.write("Could not write to logfile {0} - {1}\n".format(
                self.opts.logfile, e))

    # event format is a dict {when:time, who:[worker|logger|job|main],
    # what:str}
    def run(self):
        """
        Starts logger process
        """
        setproctitle("CoprLog")
        self.setup_log_handler()

        try:
            while True:
                event = self.events.get()
                if "when" in event and "who" in event and "what" in event:
                    self.log(event)
        except KeyboardInterrupt:
            return


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
        if record.event.get("who") == self.who:
            return True
        else:
            return False


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


class RedisLogHandler(Process):
    """
    Single point to collect logs through redis pub/sub and write
        them through standard python logging lib
    """

    def __init__(self, opts):
        Process.__init__(self, name="log_handler")

        self.opts = opts

        self.log_dir = os.path.dirname(self.opts.log_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, mode=0o750)

        self.components = ["spawner", "terminator", "vmm", "job_grab",
                           "backend", "actions", "worker"]

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
                raise Exception("Handler received msg with unknown `who` field, msg: {}".format(event))

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
