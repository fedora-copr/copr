# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import logging
from multiprocessing import Process
import os
import sys
import time
from setproctitle import setproctitle


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
        logging.basicConfig(filename=self.opts.logfile, level=logging.DEBUG)

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
            logging.debug(msg)

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
