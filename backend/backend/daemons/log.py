# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import logging
import multiprocessing
import os
import sys
import time
import setproctitle


class CoprBackendLog(multiprocessing.Process):

    """log mechanism where items from the events queue get recorded"""

    def __init__(self, opts, events):

        # base class initialization
        multiprocessing.Process.__init__(self, name="logger")

        self.opts = opts
        self.events = events

        logdir = os.path.dirname(self.opts.logfile)
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0o750)

    def setup_log_handler(self):
        sys.stderr.write("Running setup handler {} \n".format(self.opts))
        # setup a log file to write to
        logging.basicConfig(filename=self.opts.logfile, level=logging.DEBUG)

        self.log({"when": time.time(), "who": self.__class__.__name__, "what": "Logger iniated"})

    def log(self, event):

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
                self.logfile, e))

    # event format is a dict {when:time, who:[worker|logger|job|main],
    # what:str}
    def run(self):
        setproctitle.setproctitle("CoprLog")
        self.setup_log_handler()
        abort = False
        try:
            while not abort:
                event = self.events.get()
                if "when" in event and "who" in event and "what" in event:
                    self.log(event)
        except KeyboardInterrupt:
            return
