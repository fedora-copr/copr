import json
import os

from copr_common.redis_helpers import get_redis_connection

# todo: add logging here
# from copr_backend.helpers import BackendConfigReader, get_redis_logger
# opts = BackendConfigReader().read()
# log = get_redis_logger(opts, "createrepo", "actions")

# Some reasonable limit here for exceptional (probably buggy) situations.
# This is here mostly to not overflow the execve() stack limits.
MAX_IN_BATCH = 100


class BatchedCreaterepo:
    """
    Group a "group-able" set of pending createrepo tasks, and execute
    the createrepo_c binary only once for the batch.  As a result, some
    `copr-repo` processes do slightly more work (negligible difference compared
    to overall createrepo_c cost) but some do nothing.

    Note that this is wrapped into separate class mostly to make the unittesting
    easier.

    The process goes like this:

    1. BatchedCreaterepo() is instantiated by caller.
    2. Before caller acquires createrepo lock, caller notifies other processes
       by make_request().
    3. Caller acquires createrepo lock.
    4. Caller assures that no other process already did it's task, by calling
       check_processed() method (if done, caller _ends_).  Others are now
       waiting for lock so they can not process our task in the meantime.
    5. Caller get's "unified" createrepo options that are needed by the other
       queued processes by calling options() method.  These options are then
       merged with options needed by caller's task, and createrepo_c is
       executed.  Now we are saving the resources.
    6. The commit() method is called (under lock) to notify others that they
       don't have to duplicate the efforts and waste resources.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    def __init__(self, dirname, full, add, delete, rpms_to_remove, log,
                 devel=False,
                 appstream=True,
                 backend_opts=None,
                 noop=False):
        self.noop = noop
        self.log = log
        self.dirname = dirname
        self.devel = devel
        self.appstream = appstream
        self.rpms_to_remove = rpms_to_remove

        if not backend_opts:
            self.log.error("can't get access to redis, batch disabled")
            self.noop = True
            return

        self._pid = os.getpid()
        self._json_redis_task = json.dumps({
            "appstream": appstream,
            "devel": devel,
            "add": add,
            "delete": delete,
            "full": full,
            "rpms_to_remove": rpms_to_remove,
        })

        self.notify_keys = []
        self.redis = get_redis_connection(backend_opts)

    @property
    def key(self):
        """ Our instance ID (key in Redis DB) """
        return "createrepo_batched::{}::{}".format(
            self.dirname, self._pid)

    @property
    def key_pattern(self):
        """ Redis key pattern for potential tasks we can batch-process """
        return "createrepo_batched::{}::*".format(self.dirname)

    def make_request(self):
        """ Request the task into Redis DB.  Run _before_ lock! """
        if self.noop:
            return None
        self.redis.hset(self.key, "task", self._json_redis_task)
        return self.key

    def check_processed(self, delete_if_not=True):
        """
        Drop our entry from Redis DB (if any), and return True if the task is
        already processed.  When 'delete_if_not=True, we delete the self.key
        from Redis even if the task is not yet processed (meaning that caller
        plans to finish the task right away).
        """
        if self.noop:
            return False

        status = self.redis.hget(self.key, "status") == "success"
        self.log.debug("Has already a status? %s", status)

        try:
            if not status:
                # not yet processed
                return False
        finally:
            # This is atomic operation, other processes may not re-start doing this
            # task again.  https://github.com/redis/redis/issues/9531
            if status or delete_if_not:
                self.redis.delete(self.key)

        return status

    def options(self):
        """
        Get the options from other _compatible_ (see below) Redis tasks, and
        plan the list of tasks in self.notify_keys[] that we will notify in
        commit().

        We don't merge tasks that have a different 'devel' parameter.  We
        wouldn't be able to tell what sub-tasks are to be created in/out the
        devel subdirectory.

        Similarly, we don't group tasks that have different 'appstream' value.
        That's because normally (not-grouped situation) the final state of
        repository would be order dependent => e.g. if build_A requires
        appstream metadata, and build_B doesn't, the B appstream metadata would
        be added only if build_A was processed after build_B (not vice versa).
        This problem is something we don't want to solve at options() level, and
        we want rather let two concurrent processes in race (it requires at
        least one more createrepo run, but the "appstream" flag shouldn't change
        frequently anyway).
        """
        add = set()
        delete = set()
        rpms_to_remove = set()
        full = False

        if self.noop:
            return (full, add, delete, rpms_to_remove)

        for key in self.redis.keys(self.key_pattern):
            assert key != self.key

            task_dict = self.redis.hgetall(key)
            if task_dict.get("status") is not None:
                # skip processed tasks
                self.log.info("Key %s already processed, skip", key)
                continue

            task_opts = json.loads(task_dict["task"])

            skip = False
            for attr in ["devel", "appstream"]:
                our_value = getattr(self, attr)
                if task_opts[attr] != our_value:
                    self.log.info("'%s' attribute doesn't match: %s/%s",
                                  attr, task_opts[attr], our_value)
                    skip = True
                    break

            if skip:
                continue

            # we can process this task!
            self.notify_keys.append(key)

            # inherit "full" request from others
            if task_opts["full"]:
                full = True
                add = set()

            # append "add" tasks, if that makes sense
            if not full:
                add.update(task_opts["add"])

            # always process the delete requests
            delete.update(task_opts["delete"])

            rpms_to_remove.update(task_opts["rpms_to_remove"])

            if len(self.notify_keys) >= MAX_IN_BATCH - 1:  # one is ours!
                self.log.info("Batch copr-repo limit %s reached, skip the rest",
                              MAX_IN_BATCH)
                break

        return (full, add, delete, rpms_to_remove)

    def commit(self):
        """
        Report that we processed other createrepo requests.  We don't report
        about failures, we rather kindly let the responsible processes to re-try
        the createrepo tasks.  Requires lock!
        """
        if self.noop:
            return

        for key in self.notify_keys:
            self.log.info("Notifying %s that we succeeded", key)
            self.redis.hset(key, "status", "success")
