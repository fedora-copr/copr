# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import json

import time
from setproctitle import setproctitle
import weakref

from requests import get, RequestException
from retask.task import Task
from retask.queue import Queue

from ..actions import Action
from ..constants import JOB_GRAB_TASK_END_PUBSUB, BuildStatus
from ..helpers import get_redis_connection, format_tb, get_redis_logger
from ..exceptions import CoprJobGrabError
from ..frontend import FrontendClient


# TODO: Replace entire model with asynchronous queue, so that frontend push task,
# and workers listen for them
from ..vm_manage.manager import VmManager


class CoprJobGrab(object):

    """
    Fetch jobs from the Frontend

        - submit build task to the jobs queue for workers
        - run Action handler for action tasks


    :param Munch opts: backend config
    :type frontend_client: FrontendClient
    :param lock: :py:class:`multiprocessing.Lock` global backend lock

    """

    def __init__(self, opts, frontend_client):
        # base class initialization

        self.opts = opts
        self.arch_to_group_id_map = dict()
        for group in self.opts.build_groups:
            for arch in group["archs"]:
                self.arch_to_group_id_map[arch] = group["id"]

        self.task_queues_by_arch = {}
        self.task_queues_by_group = {}

        self.added_jobs_dict = dict()  # task_id -> task dict

        self.frontend_client = frontend_client

        self.rc = None
        self.channel = None
        self.ps_thread = None

        self.log = get_redis_logger(self.opts, "backend.job_grab", "job_grab")

    def connect_queues(self):
        """
        Connects to the retask queues. One queue per builders group.
        """
        for group in self.opts.build_groups:
            queue = Queue("copr-be-{0}".format(group["id"]))
            queue.connect()

            self.task_queues_by_group[group["name"]] = queue
            for arch in group["archs"]:
                self.task_queues_by_arch[arch] = queue

    def listen_to_pubsub(self):
        """
        Listens for job reschedule queries. Spawns self.ps_thread, don't forget to stop it.
        """
        self.rc = get_redis_connection(self.opts)
        self.channel = self.rc.pubsub(ignore_subscribe_messages=True)

        self.channel.subscribe(**{JOB_GRAB_TASK_END_PUBSUB: self.on_pubsub_event})
        self.ps_thread = self.channel.run_in_thread(sleep_time=0.05)

        self.log.info("Subscribed to {} channel".format(JOB_GRAB_TASK_END_PUBSUB))

    def route_build_task(self, task):
        """
        Route build task to the appropriate queue.
        :param task: dict-like object which represent build task

        Utilized **task** keys:

            - ``task_id``
            - ``chroot``
            - ``arch``

        :return int: Count of the successfully routed tasks
        """
        count = 0
        if "task_id" in task:
            if task["task_id"] not in self.added_jobs_dict:
                arch = task["chroot"].split("-")[2]
                if arch not in self.task_queues_by_arch:
                    raise CoprJobGrabError("No builder group for architecture: {}, task: {}"
                                           .format(arch, task))

                username = task["project_owner"]
                group_id = int(self.arch_to_group_id_map[arch])
                active_jobs_count = len([t for t_id, t in self.added_jobs_dict.items()
                                         if t["project_owner"] == username])

                if active_jobs_count > self.opts.build_groups[group_id]["max_vm_per_user"]:
                    self.log.debug("User can not acquire more VM (active builds #{}), "
                                   "don't schedule more tasks".format(active_jobs_count))
                    return 0

                self.added_jobs_dict[task["task_id"]] = task

                task_obj = Task(task)
                self.task_queues_by_arch[arch].enqueue(task_obj)
                count += 1

        else:
            self.log.info("Task missing field `task_id`, raw task: {}".format(task))
        return count

    def process_action(self, action):
        """
        Run action task handler, see :py:class:`~backend.action.Action`

        :param action: dict-like object with action task
        """
        ao = Action(self.opts, action, frontend_client=self.frontend_client)
        ao.run()

    def load_tasks(self):
        """
        Retrieve tasks from frontend and runs appropriate handlers
        """
        try:
            r = get("{0}/backend/waiting/".format(self.opts.frontend_base_url),
                    auth=("user", self.opts.frontend_auth))
        except RequestException as e:
            self.log.exception("Error retrieving jobs from {}: {}"
                               .format(self.opts.frontend_base_url, e))
            return

        try:
            r_json = r.json()
        except ValueError as e:
            self.log.exception("Error getting JSON build list from FE {0}".format(e))
            return

        if r_json.get("builds"):
            self.log.debug("{0} jobs returned".format(len(r_json["builds"])))
            count = 0
            for task in r_json["builds"]:
                try:
                    count += self.route_build_task(task)
                except CoprJobGrabError as err:
                    self.log.exception("Failed to enqueue new job: {} with error: {}".format(task, err))

            if count:
                self.log.info("New build jobs: %s" % count)

        if r_json.get("actions"):
            self.log.info("{0} actions returned".format(len(r_json["actions"])))

            for action in r_json["actions"]:
                try:
                    self.process_action(action)
                except Exception as error:
                    self.log.exception("Error during processing action `{}`: {}".format(action, error))

    def on_pubsub_event(self, raw):
        # from celery.contrib import rdb; rdb.set_trace()
        if raw is None:
            return
        if "type" not in raw or raw["type"] != "message":
            self.log.warn("Missing type or wrong type in pubsub msg: {}, ignored".format(raw))
            return
        try:
            msg = json.loads(raw["data"])
            # msg: {"action": ("remove"|"reschedule"), "task_id": ..., "build_id"..., "chroot": ...}
            # Actions: "remove" simply remove `task_id` from self.added_job
            #          "reschedule" additionally call frontend and set pending state before removal
            if "action" not in msg:
                self.log.warn("Missing required field `action`, msg ignored: {}".format(msg))
                return
            action = msg["action"]
            if action not in ["remove", "reschedule"]:
                self.log.warn("Action `{}` not allowed, msg ignored: {} ".format(action, msg))
                return

            if "task_id" not in msg:
                self.log.warn("Missing required field `task_id`, msg ignored: {}".format(msg))
                return

            task_id = msg["task_id"]
            if action == "reschedule" and "build_id" in msg and "chroot" in msg:
                # TODO: dirty dependency to frontend, Job management should be re-done (
                self.log.info("Rescheduling task `{}`".format(task_id))
                self.frontend_client.reschedule_build(msg["build_id"], msg["chroot"])

            if task_id not in self.added_jobs_dict:
                self.log.debug("Task `{}` not present in added jobs,  msg ignored: {}".format(task_id, msg))
                return

            if action in ["remove", "reschedule"]:
                    self.added_jobs_dict.pop(task_id)
                    self.log.info("Removed task `{}` from added_jobs".format(task_id))

        except Exception as err:
            self.log.exception("Error receiving message from remove pubsub: raw msg: {}, error: {}"
                               .format(raw, err))

    def log_queue_info(self):
        if self.added_jobs_dict:
            self.log.debug("Added jobs after remove and load: {}".format(self.added_jobs_dict))
            self.log.debug("# of executed jobs: {}".format(len(self.added_jobs_dict)))

        for group, queue in self.task_queues_by_group.items():
            if queue.length > 0:
                self.log.debug("# of pending jobs for `{}`: {}".format(group, queue.length))

    def run(self):
        """
        Starts job grabber process
        """
        setproctitle("CoprJobGrab")
        self.connect_queues()
        self.listen_to_pubsub()

        self.log.info("JobGrub started.")
        try:
            while True:
                try:
                    self.load_tasks()
                    self.log_queue_info()
                    time.sleep(self.opts.sleeptime)
                except Exception as err:
                    self.log.exception("Job Grab unhandled exception: {}".format(err))

        except KeyboardInterrupt:
            return

    def terminate(self):
        if self.ps_thread:
            self.ps_thread.stop()
            self.ps_thread.join()
        super(CoprJobGrab, self).terminate()
