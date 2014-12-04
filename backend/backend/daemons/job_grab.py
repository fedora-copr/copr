# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from collections import defaultdict

from multiprocessing import Process
import time
from setproctitle import setproctitle

from requests import get, RequestException
from retask.task import Task
from retask.queue import Queue

from ..actions import Action
from ..exceptions import CoprJobGrabError
from ..frontend import FrontendClient


# TODO: Replace entire model with asynchronous queue, so that frontend push task,
# and workers listen for them
class CoprJobGrab(Process):

    """
    Fetch jobs from the Frontend
    - submit them to the jobs queue for workers
    """

    def connect_queues(self):
        # TODO: better extract connection into the dedicated method
        for group in self.opts.build_groups:
            queue = Queue("copr-be-{0}".format(group["id"]))
            queue.connect()

            for arch in group["archs"]:
                self.task_queues_by_arch[arch] = queue

    def __init__(self, opts, events, lock):
        # base class initialization
        Process.__init__(self, name="jobgrab")

        self.opts = opts
        self.events = events
        self.task_queues_by_arch = {}

        self.added_jobs = set()
        self.lock = lock

    def event(self, what):
        self.events.put({"when": time.time(), "who": "jobgrab", "what": what})

    def process_build_task(self, task):
        count = 0
        if "task_id" in task and task["task_id"] not in self.added_jobs:
            # this will ignore and throw away unconfigured architectures
            # FIXME: don't do ^

            # TODO: produces memory leak!
            self.added_jobs.add(task["task_id"])
            arch = task["chroot"].split("-")[2]
            if arch not in self.task_queues_by_arch:
                raise CoprJobGrabError("No builder group for architecture: {}, task: {}"
                                       .format(arch, task))

            task_obj = Task(task)
            self.task_queues_by_arch[arch].enqueue(task_obj)
            count += 1
        return count

    def process_action(self, action):
        ao = Action(self.events, action, self.lock, destdir=self.opts.destdir,
                    frontend_callback=FrontendClient(self.opts, self.events),
                    front_url=self.opts.frontend_base_url,
                    results_root_url=self.opts.results_baseurl)
        ao.run()

    def load_tasks(self):
        try:
            r = get("{0}/waiting/".format(self.opts.frontend_url),
                    auth=("user", self.opts.frontend_auth))
        except RequestException as e:
            self.event("Error retrieving jobs from {0}: {1}"
                       .format(self.opts.frontend_url, e))
            return

        try:
            r_json = r.json()
        except ValueError as e:
            self.event("Error getting JSON build list from FE {0}".format(e))
            return

        if r_json.get("builds"):
            self.event("{0} jobs returned".format(len(r_json["builds"])))
            count = 0
            for task in r_json["builds"]:
                try:
                    count += self.process_build_task(task)
                except CoprJobGrabError as err:
                    self.event("Failed to enqueue new job: {} with error: {}"
                               .format(task, err))

            if count:
                self.event("New jobs: %s" % count)

        if r_json.get("actions"):
            self.event("{0} actions returned".format(len(r_json["actions"])))

            for action in r_json["actions"]:
                self.process_action(action)

    def run(self):
        setproctitle("CoprJobGrab")
        self.connect_queues()
        try:
            while True:
                self.load_tasks()
                time.sleep(self.opts.sleeptime)
        except KeyboardInterrupt:
            return
