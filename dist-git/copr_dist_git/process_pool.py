from multiprocessing import Process

import datetime
import logging

from .exceptions import TimeoutException

log = logging.getLogger(__name__)


class Worker(Process):
    def __init__(self, id=None, timeout=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.id = id
        self.timeout = timeout
        self.timestamp = datetime.datetime.now()

    @property
    def timeouted(self):
        return datetime.datetime.now() >= self.timestamp + datetime.timedelta(seconds=self.timeout)


class SingleThreadWorker(Worker):
    def start(self):
        self.run()


class Pool(list):
    def __init__(self, workers=None, *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        self.workers = workers

    @property
    def busy(self):
        # There is running job on every core
        return len(self) >= self.workers

    def terminate_timeouted(self, callback):
        for worker in filter(lambda w: w.timeouted, self):
            log.info("Going to terminate worker '{}' with task '{}' due to exceeded timeout {} seconds"
                     .format(worker.name, worker.id, worker.timeout))
            worker.terminate()
            callback({"build_id": worker.id, "error": TimeoutException.strtype})
            log.info("Worker '{}' with task '{}' was terminated".format(worker.name, worker.timeout))

    def remove_dead(self):
        for worker in filter(lambda w: not w.is_alive(), self):
            if worker.exitcode == 0:
                log.info("Worker '{}' finished task '{}'".format(worker.name, worker.id))
            log.info("Removing worker '{}' with task '{}' from pool".format(worker.name, worker.id))
            self.remove(worker)
