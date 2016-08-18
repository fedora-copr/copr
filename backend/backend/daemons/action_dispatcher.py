# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import json
import time
import multiprocessing
from setproctitle import setproctitle
from requests import get, RequestException

from backend.frontend import FrontendClient

from ..actions import Action
from ..helpers import get_redis_logger


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

    def load_action(self):
        """
        Retrieve an action task from frontend.
        """
        self.log.info("Waiting for an action task from frontend...")
        get_action_init_time = time.time()

        action_task = None
        while not action_task:
            self.update_process_title("Waiting for an action task from frontend for {}s"
                                      .format(int(time.time() - get_action_init_time)))
            try:
                r = get("{0}/backend/waiting/".format(self.opts.frontend_base_url),
                        auth=("user", self.opts.frontend_auth))
                action_task = r.json().get("action")
            except (RequestException, ValueError) as error:
                self.log.exception("Retrieving an action task from {} failed with error: {}"
                                   .format(self.opts.frontend_base_url, error))
            finally:
                if not action_task:
                    time.sleep(self.opts.sleeptime)

        self.log.info("Got new action_task {} of type {}".format(action_task['id'], action_task['action_type']))
        return Action(self.opts, action_task, frontend_client=self.frontend_client)

    def run(self):
        """
        Executes action dispatching process.
        """
        self.log.info("Action dispatching started.")
        self.update_process_title()

        while True:
            action = self.load_action()
            try:
                action.run()
            except Exception as e: # dirty
                self.log.exception(e)
            msg = "Started new action {} of type {}"\
                  .format(action.data["id"], action.data["action_type"])
            self.update_process_title(msg)
            self.log.info(msg)
