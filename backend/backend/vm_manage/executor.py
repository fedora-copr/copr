# coding: utf-8
import threading
import time
from ..helpers import get_redis_logger


class Executor(object):
    """
    Helper super-class to run background processes and clean up after them.

    Child class should have method which spawns subprocess and add it handler to `self.child_processes` list.
    Also don't forget to call recycle
    """
    __name_for_log__ = "executor"
    __who_for_log__ = "executor"

    def __init__(self, opts):
        self.opts = opts

        self.child_processes = []
        self.last_recycle = time.time()
        self.recycle_period = 60

        self.log = get_redis_logger(self.opts, "vmm.{}".format(self.__name_for_log__), self.__who_for_log__)

    def run_detached(self, func, args):
        """
        Abstaction to spawn Thread or Process
        :return:
        """
        # proc = Process(target=func, args=(args))
        proc = threading.Thread(target=func, args=args)
        self.child_processes.append(proc)
        proc.start()
        # self.log.debug("Spawn process started: {}".format(proc.pid))
        return proc

    def after_proc_finished(self, proc):
        # hook for subclasses
        pass

    def recycle(self, force=False):
        """
        Cleanup unused process, should be invoked periodically
        :param force: do recycle now unconditionally
        :type force: bool
        """
        if not force and time.time() - self.last_recycle < self.recycle_period:
            return

        self.last_recycle = time.time()

        self.log.debug("Running recycle {}")
        still_alive = []
        for proc in self.child_processes:
            if proc.is_alive():
                still_alive.append(proc)
            else:
                proc.join()
                # self.log.debug("Child process finished: {}".format(proc.pid))
                self.log.debug("Child process finished: %s", proc)
                self.after_proc_finished(proc)

        self.child_processes = still_alive

    def terminate(self):
        for proc in self.child_processes:
            proc.terminate()
            proc.join()

    @property
    def children_number(self):
        self.recycle()
        return len(self.child_processes)
