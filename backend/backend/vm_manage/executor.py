# coding: utf-8
import time


class Executor(object):
    """
    Helper super-class to run background processes and clean up after them.

    Child class should have method which spawns subprocess and add it handler to `self.child_processes` list.
    Also don't forget to call recycle
    """
    __name_for_log__ = "executor"

    def __init__(self, opts, events):
        self.opts = opts
        self.events = events

        self.child_processes = []
        self.last_recycle = time.time()
        self.recycle_period = 60

    def log(self, msg, who=None):
        self.events.put({"when": time.time(),
                         "who": who or self.__name_for_log__,
                         "what": msg})

    def recycle(self, force=False):
        """
        Cleanup unused process, should be invoked periodically
        :param force: do recycle now unconditionally
        :type force: bool
        """
        if not force and time.time() - self.last_recycle < self.recycle_period:
            return
        self.log("Running recycle")
        still_alive = []
        for proc in self.child_processes:
            if proc.is_alive():
                still_alive.append(proc)
            else:
                proc.join()
                self.log("Child process finished: {}".format(proc.pid))
        self.child_processes = still_alive

    def terminate(self):
        for proc in self.child_processes:
            proc.terminate()
            proc.join()


    @property
    def children_number(self):
        self.recycle()
        return len(self.child_processes)
