# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import multiprocessing
import time
import setproctitle

import requests
from retask.task import Task
from retask.queue import Queue

from backend.actions import Action
from backend.frontend import FrontendClient


class CoprJobGrab(multiprocessing.Process):

    """
    Fetch jobs from the Frontend
    - submit them to the jobs queue for workers
    """

    def __init__(self, opts, events, lock):
        # base class initialization
        multiprocessing.Process.__init__(self, name="jobgrab")

        self.opts = opts
        self.events = events
        self.task_queues = []
        for group in self.opts.build_groups:
            self.task_queues.append(Queue("copr-be-{0}".format(group["id"])))
            self.task_queues[group["id"]].connect()
        self.added_jobs = []
        self.lock = lock

    def event(self, what):
        self.events.put({"when": time.time(), "who": "jobgrab", "what": what})

    def process_build_task(self, task):
        count = 0
        if "task_id" in task and task["task_id"] not in self.added_jobs:
            # this will ignore and throw away unconfigured architectures
            # FIXME: don't do ^
            arch = task["chroot"].split("-")[2]
            for group in self.opts.build_groups:
                if arch in group["archs"]:
                    self.added_jobs.append(task["task_id"])
                    task_obj = Task(task)
                    self.task_queues[group["id"]].enqueue(task_obj)
                    count += 1
                    break
        return count

    def process_action(self, action):
        ao = Action(self.events, action, self.lock, destdir=self.opts.destdir,
                    frontend_callback=FrontendClient(self.opts, self.events),
                    front_url=self.opts.frontend_base_url,
                    results_root_url=self.opts.results_baseurl)
        ao.run()

    def load_tasks(self):
        try:
            r = requests.get("{0}/waiting/".format(self.opts.frontend_url),
                             auth=("user", self.opts.frontend_auth))
            r_json = r.json()

        except requests.RequestException as e:
            self.event("Error retrieving jobs from {0}: {1}".format(
                       self.opts.frontend_url, e))
            return

        except ValueError as e:
            self.event("Error getting JSON build list from FE {0}"
                       .format(e))
            return

        if "builds" in r_json and r_json["builds"]:
            self.event("{0} jobs returned".format(len(r_json["builds"])))
            count = 0
            for task in r_json["builds"]:
                count += self.process_build_task(task)
            if count:
                self.event("New jobs: %s" % count)

        if "actions" in r_json and r_json["actions"]:
            self.event("{0} actions returned".format(len(r_json["actions"])))

            for action in r_json["actions"]:
                self.process_action(action)

    def run(self):
        setproctitle.setproctitle("CoprJobGrab")
        abort = False
        try:
            while not abort:
                self.load_tasks()
                time.sleep(self.opts.sleeptime)
        except KeyboardInterrupt:
            return
