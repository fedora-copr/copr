from retask.queue import Queue
from retask.task import Task

from .helpers import wait_log

class Channel(object):
    """
    Abstraction above retask (the set of "channels" between backend(s),
    jobgrabber and workers).  We could use multiple backends and/or diffferent
    "atomic" medium (other implemntation than Queue) in future.  But
    make sure nobody needs to touch the "medium" directly.
    """

    def __init__(self, opts, log=None):
        self.log = log
        self.opts = opts
        # channel for Backend <--> JobGrabber communication
        self.jg_start = Queue("jg_control_start")
        # channel for JobGrabber <--> [[Builders]] communication
        self.build_queues = dict()
        while not self.jg_start.connect():
            wait_log("waiting for redis", 5)

    def _get_queue(self, bgroup):
        if not bgroup in self.build_queues:
            q_id = "copr-be-{0}".format(bgroup)
            q = Queue(q_id)
            if not q.connect():
                # As we already connected to jg_control_message, this should
                # be also OK.
                raise Exception("can't connect to redis, should never happen!")
            return q

        return self.build_queues[bgroup]

    def add_build(self, bgroup, build):
        """ this should be used by job_grab only for now """
        q = self._get_queue(bgroup)
        try:
            q.enqueue(Task(build))
        except Exception as err:
            # I've seen isses Task() was not able to jsonify urllib exceptions
            if not self.log:
                return False
            self.log.error("can't enqueue build {0}, reason:\n{1}".format(
                build, err
            ))

        return True

    # Builder's API
    def get_build(self, bgroup):
        """
        Return task from queue or return 0
        """
        q = self._get_queue(bgroup)
        t = q.dequeue()
        return t.data if t else None

    # JobGrab's API
    def backend_started(self):
        return self.jg_start.length

    def job_graber_initialized(self):
        while self.jg_start.dequeue():
            pass

    def remove_all_builds(self):
        for bgroup in self.build_queues:
            q = self._get_queue(bgroup)
            while q.dequeue():
                pass
        self.build_queues = dict()

    # Backend's API
    def backend_start(self):
        """ Notify jobgrab about service start. """
        self.jg_start.enqueue("start")
        while self.jg_start.length:
            wait_log(self.log, "waiting until jobgrabber initializes queue")
