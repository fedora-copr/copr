"""
example of cancellable thread task
"""

import threading
import logging


def _stderr_logger():
    logging.basicConfig(level=logging.DEBUG)
    return logging.getLogger('root')


class CancellableThreadTask:
    """
    Start ``method`` in background thread, and wait for external "cancel" event
    (when ``cb_check_canceled`` returns True).  When the "cancel" event happens,
    call the ``cb_cancel`` calback.
    """

    # pylint: disable=too-many-arguments,too-few-public-methods
    def __init__(self, method, cb_check_canceled, cb_cancel,
                 check_period=5, log=None):
        self.method = method
        self.check = cb_check_canceled
        self.cancel = cb_cancel
        self.result = None
        self.check_period = check_period
        self.log = log or _stderr_logger()

    @staticmethod
    def _background_run_wrapper(call, result, *args, **kwargs):
        result.result = call(*args, **kwargs)

    def run(self, *args, **kwargs):
        """ execute the self.method with args/kwargs """
        self.log.debug("starting background method: %s", self.method)
        thread = threading.Thread(
            target=self._background_run_wrapper,
            args=(self.method, self) + args,
            kwargs=kwargs,
        )
        thread.start()
        while True:
            self.log.debug("checking liveness")
            thread.join(timeout=self.check_period)
            if not thread.is_alive():
                self.log.debug("thread ended")
                break

            if self.check(*args, **kwargs):
                self.log.debug("calling cancel callback, and waiting")
                self.cancel(*args, **kwargs)
                thread.join()
                break

        return self.result
