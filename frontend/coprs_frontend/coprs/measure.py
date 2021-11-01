"""
Helper methods for measuring flask performance.
"""

import datetime

from coprs import app

CONTEXT = None


class CheckPointContext:
    """
    the checkpoint's CONTEXT variable
    """
    def __init__(self):
        self.start = datetime.datetime.now()
        self.last = self.start


def checkpoint_start(force=False):
    """
    Enable checkpoints by flask global variable.
    """
    global CONTEXT  # pylint: disable=global-statement
    if force or app.config["DEBUG_CHECKPOINTS"]:
        CONTEXT = CheckPointContext()


def checkpoint(message):
    """
    Print useful timing info for the CONTEXT, prefixed with MESSAGE.
    You can enable this by `DEBUG_CHECKPOINTS = True` config option, or
    by calling `checkpoint_start(force=True)`.  Usage:

        checkpoint("start")
        some_expensive_action()
        checkpoint("Expensive action finished")

    Then the stdout output is:

        start                         : 0:00:00.148130 (full time 0:00:00.148130)
        Expensive action finished     : 0:00:04.223232 (full time 0:00:04.371362)
    """

    if CONTEXT is None:
        return
    start = CONTEXT.start
    last = CONTEXT.last
    now = datetime.datetime.now()

    app.logger.info("%30s: %s (full time %s)",
                    message, now-last, now-start)
    CONTEXT.last = now
