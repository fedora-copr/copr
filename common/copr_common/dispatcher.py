"""
Abstract class Dispatcher for Build/Action dispatchers.
"""

import time
import logging
import multiprocessing
from setproctitle import setproctitle

from copr_common.redis_helpers import get_redis_connection
from copr_common.worker_manager import WorkerManager


class Dispatcher(multiprocessing.Process):
    """
    1) Fetch tasks from frontend.
    2) Fill the WorkerManager queue.
    3) Run 'WorkerManager.run()'.
    4) Go to 1)

    See also:
    https://docs.pagure.org/copr.copr/developer_documentation/dispatchers.html
    https://docs.pagure.org/copr.copr/developer_documentation/worker_manager.html
    """

    # set to either 'action' or 'build' in sub-class
    task_type = 'task_type'

    # either ActionWorkerManager or BuildWorkerManager
    worker_manager_class = WorkerManager

    # how many background workers we let the WorkerManager start, by default
    # there's no limit
    max_workers = float("inf")

    # we keep track what build's newly appeared in the task list after fetching
    # the new set from frontend after get_frontend_tasks() call
    _previous_task_fetch_ids = set()

    def __init__(self, opts):
        super().__init__(name=self.task_type + '-dispatcher')

        self.sleeptime = 0
        self.opts = opts
        self.log = logging.getLogger()
        self.frontend_client = None
        # list of applied WorkerLimit instances
        self.limits = []

    @classmethod
    def _update_process_title(cls, msg=None):
        proc_title = "{} dispatcher".format(cls.task_type.capitalize())
        if msg:
            proc_title += " - " + msg
        setproctitle(proc_title)

    def get_frontend_tasks(self):
        """
        Get _unfiltered_ list of tasks (QueueTask objects) from frontend (the
        set needs to contain both running and pending jobs).
        """
        raise NotImplementedError

    def get_cancel_requests_ids(self):
        """
        Return list of QueueTask IDS that should be canceled.
        """
        _subclass_can_use = (self)
        return []

    def report_canceled_task_id(self, task_id, was_running):
        """
        Report back to Frontend that this task was canceled.  By default this
        isn't called, so it is NO-OP by default.
        """

    def _print_added_jobs(self, tasks):
        job_ids = {task.id for task in tasks}
        new_job_ids = job_ids - self._previous_task_fetch_ids
        if new_job_ids:
            self.log.info("Got new '%s' tasks: %s", self.task_type, new_job_ids)
        self._previous_task_fetch_ids = job_ids

    def run(self):
        """
        Starts the infinite task dispatching process.
        """
        self.log.info("%s dispatching started", self.task_type.capitalize())
        self._update_process_title()

        redis = get_redis_connection(self.opts)
        worker_manager = self.worker_manager_class(
            redis_connection=redis,
            log=self.log,
            max_workers=self.max_workers,
            frontend_client=self.frontend_client,
            limits=self.limits,
        )

        timeout = self.sleeptime
        while True:
            self._update_process_title("getting tasks from frontend")
            self.log.info("getting %ss from frontend", self.task_type)
            start = time.time()

            tasks = self.get_frontend_tasks()
            if tasks:
                worker_manager.clean_tasks()

            self._print_added_jobs(tasks)
            for task in tasks:
                worker_manager.add_task(task)

            self._update_process_title("getting cancel requests")
            for task_id in self.get_cancel_requests_ids():
                was_running = worker_manager.cancel_task_id(task_id)
                self.report_canceled_task_id(task_id, was_running)

            # process the tasks
            self._update_process_title("processing tasks")
            worker_manager.run(timeout=timeout)

            sleep_more = timeout - (time.time() - start)
            if sleep_more > 0:
                time.sleep(sleep_more)

        # reset the title
        self._update_process_title()
