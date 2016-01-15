# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import json

import time
from setproctitle import setproctitle

from requests import get, RequestException

from backend.frontend import FrontendClient

from ..actions import Action
from ..constants import JOB_GRAB_TASK_END_PUBSUB
from ..helpers import get_redis_connection, get_redis_logger
from ..exceptions import CoprJobGrabError
from .. import jobgrabcontrol

# TODO: Replace entire model with asynchronous queue, so that frontend push task,
# and workers listen for them
# praiskup: Please don't.  I doubt this would help too much, and I really don't
# think it is worth another rewrite.  Reasons (imho):
#   a. there still needs to be "one" organizator, aka jobgrabber on the backend
#      VM side -- we do not want allow Workers to contact frontend directly
#      because of (1) security and (2) process synchronization.
#   b. in frontend, we _never_ want to block UI differently than on database,
#      so the push to BE can't be done instantly -- and thus there would have
#      to be something like buffered "JobPusher" (and that would be most
#      probably implemented as poll anyway).  Maybe we could use some "pipe"
#      approach through infinite (http?) connection, or opened database
#      connection, .. but I don't think it does matter too much who will
#      control the "pipe".
class CoprJobGrab(object):

    """
    Fetch jobs from the Frontend

        - submit build task to the jobs queue for workers
        - run Action handler for action tasks


    :param Munch opts: backend config
    :param lock: :py:class:`multiprocessing.Lock` global backend lock

    TODO: Not yet fully ready for config reload.
    """

    def __init__(self, opts):
        """ base class initialization """

        self.opts = opts

        # Maps e.g. x86_64 && i386 => PC (.
        self.arch_to_group_id_map = dict()
        # PC => max N builders per user
        self.group_to_usermax = dict()
        # task_id -> task dict
        self.added_jobs_dict = dict()

        self.rc = None
        self.channel = None
        self.ps_thread = None

        self.log = get_redis_logger(self.opts, "backend.job_grab", "job_grab")
        self.jg_control = jobgrabcontrol.Channel(self.opts, self.log)
        self.frontend_client = FrontendClient(self.opts, self.log)


    def group(self, arch):
        return self.arch_to_group_id_map[arch]


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
                group = self.group(arch)

                username = task["project_owner"]
                active_jobs_count = len([t for t_id, t in self.added_jobs_dict.items()
                                         if t["project_owner"] == username])

                if active_jobs_count > self.group_to_usermax[group]:
                    self.log.debug("User can not acquire more VM (active builds #{0}), "
                                   "don't schedule more tasks".format(active_jobs_count))
                    return 0

                msg = "enqueue task for user {0}: id={1}, arch={2}, group={3}, active={4}"
                self.log.debug(msg.format(username, task["task_id"], arch, group, active_jobs_count))

                # Add both to local list and control channel queue.
                self.added_jobs_dict[task["task_id"]] = task
                self.jg_control.add_build(group, task)
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
            count = 0
            self.log.info("{0} actions returned".format(len(r_json["actions"])))

            for action in r_json["actions"]:
                start = time.time()
                try:
                    self.process_action(action)
                except Exception as error:
                    self.log.exception("Error during processing action `{}`: {}".format(action, error))
                if time.time() - start > 2*self.opts.sleeptime:
                    # we are processing actions for too long, stop and fetch everything again (including new builds)
                    break
                    

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


    def init_internal_structures(self):
        self.arch_to_group_id_map = dict()
        self.group_to_usermax = dict()
        for group in self.opts.build_groups:
            group_id = group["id"]
            for arch in group["archs"]:
                self.arch_to_group_id_map[arch] = group_id
                self.log.debug("mapping {0} to {1} group".format(arch, group_id))

            self.log.debug("user might use only {0}VMs for {1} group".format(group["max_vm_per_user"], group_id))
            self.group_to_usermax[group_id] = group["max_vm_per_user"]

        self.added_jobs_dict = dict()


    def handle_control_channel(self):
        if not self.jg_control.backend_started():
            return
        self.log.info("backend gave us signal to start")
        self.init_internal_structures()
        self.jg_control.remove_all_builds()
        self.jg_control.job_graber_initialized()

    def run(self):
        """
        Starts job grabber process
        """
        setproctitle("CoprJobGrab")
        self.listen_to_pubsub()

        self.log.info("JobGrub started.")

        self.init_internal_structures()
        try:
            while True:
                try:
                    # This effectively delays job_grabbing until backend
                    # gives as signal to start.
                    self.handle_control_channel()
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
