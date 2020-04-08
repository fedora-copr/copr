# coding: utf-8

import time
import multiprocessing
from setproctitle import setproctitle

from copr_backend.frontend import FrontendClient
from copr_backend.exceptions import FrontendClientException

from ..actions import ActionWorkerManager, ActionQueueTask, Action
from ..helpers import get_redis_logger, get_redis_connection


class ActionDispatcher(multiprocessing.Process):
    """
    1) Fetch action task from frontend
    2) Run it synchronously
    3) Go to 1)
    """

    def __init__(self, opts):
        multiprocessing.Process.__init__(self, name="action-dispatcher")

        self.opts = opts
        self.log = get_redis_logger(self.opts, "backend.action_dispatcher", "action_dispatcher")
        self.frontend_client = FrontendClient(self.opts, self.log)

    def update_process_title(self, msg=None):
        proc_title = "Action dispatcher"
        if msg:
            proc_title += " - " + msg
        setproctitle(proc_title)

    def get_frontend_actions(self):
        """
        Get unfiltered list of actions from frontend, both running and pending.
        """

        try:
            raw_actions = self.frontend_client.get('pending-actions').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception(
                "Retrieving an action tasks failed with error: %s",
                error)
            return []

        return [ActionQueueTask(Action(self.opts, action, log=self.log))
                for action in raw_actions]


    def run(self):
        """
        Executes action dispatching process.
        """
        self.log.info("Action dispatching started.")
        self.update_process_title()

        redis = get_redis_connection(self.opts)
        worker_manager = ActionWorkerManager(
            redis_connection=redis,
            log=self.log,
            max_workers=self.opts.actions_max_workers)
        worker_manager.frontend_client = FrontendClient(self.opts, self.log)

        timeout = self.opts.sleeptime

        while True:
            self.log.info("getting actions from frontend")
            start = time.time()
            for task in self.get_frontend_actions():
                worker_manager.add_task(task)

            # Execute the actions.
            worker_manager.run(timeout=timeout)

            sleep_more = timeout - (time.time() - start)
            if sleep_more > 0:
                time.sleep(sleep_more)
