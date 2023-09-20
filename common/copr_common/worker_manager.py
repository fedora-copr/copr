"""
WorkerManager for processing a priority queue and starting background jobs
"""

import os
import time
from heapq import heappop, heappush
import itertools
import logging
import subprocess


class WorkerLimit:
    """
    Limit for the number of tasks being processed concurrently

    WorkerManager expects that it's caller fills the task queue only with tasks
    that should be processed.  Then WorkerManager is completely responsible for
    sorting out the queue, and behave -> respect the given limits.

    WorkerManager implements really stupid algorithm to respect the limits;  we
    simply drop the task from queue (and continue to the next task) if it was
    about to exceed any given limit.  This is the only option at this moment
    because JobQueue doesn't allow us to skip some task, and return to it later.
    It is not a problem for Copr dispatchers though because we re-add the
    dropped tasks to JobQueue anyways -- after the next call to the
    Dispatcher.get_frontend_tasks() method (see "sleeptime" configuration
    option).

    Each Limit object works as a statistic counter for the list of _currently
    processed_ tasks (i.e. not queued tasks!).  And we may want to query the
    statistics anytime we want to.  Both calculating and querying the statistics
    must be as fast as possible, therefore the interface only re-calculates the
    stats when WorkerManager starts/stops working on some task.

    One may wonder why to bother with limits, and why not to delegate this
    responsibility on WorkerManager caller (IOW don't put the task to queue if
    it is not yet the right time process it..).  That would be ideal case, but
    at the time of filling the queue caller has no idea about the currently
    running BackgroundWorker instances (those need to be calculated to
    statistics, too).
    """

    def __init__(self, name=None):
        self._name = name

    def worker_added(self, worker_id, task):
        """ Add worker and it's task to statistics.  """
        raise NotImplementedError

    def check(self, task):
        """ Check if the task can be added without crossing the limit. """
        raise NotImplementedError

    def clear(self):
        """ Clear the statistics. """
        raise NotImplementedError

    def info(self):
        """ Get the user-readable info about the limit object """
        if self._name:
            return "'{}'".format(self._name)
        return "Unnamed '{}' limit".format(type(self).__name__)


class PredicateWorkerLimit(WorkerLimit):
    """
    Calculate how many tasks being processed by currently running workers match
    the given predicate.
    """
    def __init__(self, predicate, limit, name=None):
        """
        :param predicate: function object taking one QueueTask argument, and
            returning True or False
        :param limit: how many tasks matching the ``predicate`` are allowed to
            be processed concurrently.
        """
        super().__init__(name)
        self._limit = limit
        self._predicate = predicate
        self.clear()

    def clear(self):
        self._refs = {}

    def worker_added(self, worker_id, task):
        if not self._predicate(task):
            return
        self._refs[worker_id] = True

    def check(self, task):
        if not self._predicate(task):
            return True
        return len(self._refs) < self._limit

    def info(self):
        text = super().info()
        matching = ', '.join(self._refs.keys())
        if not matching:
            return text
        return "{}, matching: {}".format(text, matching)


class StringCounter:
    """
    Counter for string occurrences.  When string is None, we don't count it
    """
    def __init__(self):
        self._counter = {}

    def add(self, string):
        """ Add string to counter """
        if string is None:
            return
        if string in self._counter:
            self._counter[string] += 1
        else:
            self._counter[string] = 1

    def count(self, string):
        """ Return number ``string`` occurrences """
        return self._counter.get(string, 0)

    def __str__(self):
        items = ["{}={}".format(key, value)
                 for key, value in self._counter.items()]
        return ", ".join(items)


class HashWorkerLimit(WorkerLimit):
    """
    Assign tasks to groups per the return value of the HASHER(TASK) method.  Set
    maximum number of workers **per each such group**.
    """
    def __init__(self, hasher, limit, name=None):
        """
        :param hasher: function object taking one QueueTask argument, and
            returning string key (name of the ``group``).
        :param limit: how many tasks in the ``group`` are allowed to be
            processed at the same time.
        """
        super().__init__(name)
        self._limit = limit
        self._hasher = hasher
        self.clear()

    def clear(self):
        self._groups = StringCounter()
        self._refs = {}

    def worker_added(self, worker_id, task):
        # remember it
        group_name = self._refs[worker_id] = self._hasher(task)
        # count it
        self._groups.add(group_name)

    def check(self, task):
        group_name = self._hasher(task)
        return self._groups.count(group_name) < self._limit

    def info(self):
        text = super().info()
        return "{}, counter: {}".format(text, str(self._groups))


class JobQueue():
    """
    Priority "task" queue for WorkerManager.  Taken from:
    https://docs.python.org/3/library/heapq.html#priority-queue-implementation-notes
    The higher the 'priority' is, the later the task is taken.
    """

    def __init__(self, removed='<removed-task>'):
        self.prio_queue = []             # list of entries arranged in a heap
        self.entry_finder = {}           # mapping of tasks to entries
        self.removed = removed           # placeholder for a removed task
        self.counter = itertools.count() # unique sequence count

    def add_task(self, task, priority=0):
        'Add a new task or update the priority of an existing task'
        if repr(task) in self.entry_finder:
            self.remove_task(task)
        count = next(self.counter)
        entry = [priority, count, task]
        self.entry_finder[repr(task)] = entry
        heappush(self.prio_queue, entry)

    def remove_task(self, task):
        'Mark an existing task as removed.  Raise KeyError if not found.'
        self.remove_task_by_id(repr(task))

    def remove_task_by_id(self, task_id):
        """
        Using task id, drop the task from queue.  Raise KeyError if not found.
        """
        entry = self.entry_finder.pop(task_id)
        entry[-1] = self.removed

    def pop_task(self):
        'Remove and return the lowest priority task. Raise KeyError if empty.'
        while self.prio_queue:
            _priority, _count, task = heappop(self.prio_queue)
            if task is not self.removed:
                del self.entry_finder[repr(task)]
                return task
        raise KeyError('pop from an empty priority queue')


class QueueTask:
    """
    A base class for tasks processed by `Dispatcher` implementations
    """

    def __repr__(self):
        return str(self.id)

    @property
    def id(self):
        """
        Unique ID for distinguishing tasks
        """
        raise NotImplementedError

    @property
    def priority(self):
        """
        The higher the 'priority' is, the later the task is taken.
        """
        return 0


class WorkerManager():
    """
    Automatically process 'self.tasks' priority queue, and start background jobs
    to handle them.

    :cvar worker_prefix: Unique string across all the WorkerManager child
            classes, this is used as prefix for the workers in redis database
            and to easily determine to which WorkerManager the particlar worker
            belongs to.  So it can be anything reasonable, just make sure it is
            unique.
    :cvar worker_timeout_start: The time period we give the background process
            successfully start and identify itself (see has_worker_started()
            method).  If the background process isn't indentified after this
            timeout, we drop it from database and consider it failed.  And the
            task is re-scheduled.  Float value in seconds.
    :cvar worker_timeout_deadcheck: If the worker successfully identified itself
            after start (the has_worker_started() returns True) we know that the
            worker process at least started.  But after worker_timeout_deadcheck
            timeout we'll also keep an eye on the process by asking the
            is_worker_alive() method - whether the task is really still doing
            something on background or not (== unexpected failure cleanup).
            Fill float value in seconds.
    :cvar worker_cleanup_period: How often should WorkerManager try to cleanup
            workers? (value is a period in seconds)
    """

    # pylint: disable=too-many-instance-attributes

    worker_prefix = 'worker' # make sure this is unique in each class
    worker_timeout_start = 30
    worker_timeout_deadcheck = 3*60
    worker_cleanup_period = 3.0


    def __init__(self, redis_connection=None, max_workers=8, log=None,
                 frontend_client=None, limits=None):
        self.tasks = JobQueue()
        self.log = log if log else logging.getLogger()
        self.redis = redis_connection
        self.max_workers = max_workers
        self.frontend_client = frontend_client
        # We have to frequently ask for the actually tracked list of workers —
        # therefore we keep it here to not re-query the list from Redis all the
        # time.  We have to load the list from Redis initially, when the process
        # starts (Manager/Dispatcher class is loaded) because we want the logic
        # to survive server restarts (we adopt the old background workers).
        self._tracked_workers = set(self.worker_ids())
        self._limits = limits or []
        self._last_worker_cleanup = None

    def start_task(self, worker_id, task):
        """
        Start background job using the 'task' object taken from the 'tasks'
        queue.  The background task should _on its own_ and ASAP let the manager
        know that it successfully started (e.g. mark the job 'started' in redis
        DB), so the has_worker_started() method later gives us valid info.
        That's btw. the reason why we have the mandatory `worker_id` argument
        here, the background worker needs to know what key to update in redis.
        """
        raise NotImplementedError

    def finish_task(self, worker_id, task_info):
        """
        This is called once the worker manager consider the task to be done,
        because the `has_worker_ended()` method already returns True.  Override
        this function and use it to let Frontend know that the task finished,
        and how (whether it succeeded, etc.).
        """
        raise NotImplementedError

    def has_worker_started(self, worker_id, task_info):
        """
        The background task process should somehow notify manager that it
        already started (so we can have has_worker_started() implemented).
        By default we expect it sets 'started' attribute in redis DB, but feel
        free to override this method and invent different notification
        mechanism.
        """
        # pylint: disable=no-self-use
        # pylint: disable=unused-argument
        return 'started' in task_info

    def has_worker_ended(self, worker_id, task_info):
        """
        Check 'task_info' (dictionary output from redis) whether the task is
        already finished by worker.  If yes, do whatever is needed with the
        result (contact frontend) and return True.  If the task is still
        processed, return False.  By default we just check for the ``status``
        presence in ``task_info``, but this method is to be overridden.
        """
        _subclass_can_use = (self, worker_id)
        return 'status' in task_info

    def is_worker_alive(self, worker_id, task_info):
        """
        Check staled jobs on background, whether they haven't died before they
        notified us about the status.  We'll keep asking after
        worker_timeout_deadcheck seconds left since we tried to spawn the
        worker.

        By default we check for 'PID' presence in task_info, but users are
        advised to override this method when necessary.  We keep the 'self'
        and 'worker_id' arguments as they might be useful.
        """
        # pylint: disable=unused-argument,no-self-use
        if not 'PID' in task_info:
            return False
        pid = int(task_info['PID'])
        try:
            # Send signal=0 to the process to check whether it still exists.
            # This is just no-op if the signal was successfully delivered to
            # existing process, otherwise exception is raised.
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def get_worker_id(self, task_id):
        """
        Given the unique task representation form (usually ID), generate worker
        identificator (redis key).
        """
        return '{}:{}'.format(self.worker_prefix, task_id)

    def get_task_id_from_worker_id(self, worker_id):
        """
        Given the unique task representation form (usually ID), generate worker
        identificator (redis key).
        """
        prefix, task_id = worker_id.rsplit(':', 1)
        assert prefix == self.worker_prefix
        return task_id

    def _calculate_limits_for_task(self, worker_id, task):
        for limit in self._limits:
            limit.worker_added(worker_id, task)

    def cancel_request_done(self, task):
        """ Report back to frontend that the cancel request was finished. """

    def add_task(self, task):
        """
        Add task to queue.
        """
        task_id = repr(task)
        worker_id = self.get_worker_id(task_id)

        if worker_id in self._tracked_workers:
            # No need to re-add this to queue, but we need to calculate
            # it into the limits.
            self._calculate_limits_for_task(worker_id, task)
            self.log.debug("Task %s already has a worker process", task_id)
            return

        self.log.debug("Adding task %s to queue, priority %s", task_id,
                       task.priority)
        self.tasks.add_task(task, task.priority)

    def _drop_task_id_safe(self, task_id):
        try:
            self.tasks.remove_task_by_id(task_id)
        except KeyError:
            pass

    def cancel_task_id(self, task_id):
        """
        Using task_id, cancel corresponding task, and request worker
        shut-down (when already started)

        :return: True if worker is running on background, False otherwise
        """
        self._drop_task_id_safe(task_id)
        worker_id = self.get_worker_id(task_id)
        if worker_id not in self.worker_ids():
            self.log.info("Cancel request, worker %s is not running", worker_id)
            return False
        self.log.info("Cancel request, worker %s requested to cancel",
                      worker_id)
        self.redis.hset(worker_id, 'cancel_request', 1)
        return True

    def worker_ids(self):
        """
        Return the redis keys representing workers running on background.
        """
        return self.redis.keys(self.worker_prefix + ':*')

    def run(self, timeout=float('inf')):
        """
        Process the task (priority) queue.
        """
        now = None
        start_time = time.time()
        self.log.debug("Worker.run() start at time %s", start_time)

        # Make sure _cleanup_workers() has some effect during the run() call.
        # This is here mostly for the test-suite, because in the real use-cases
        # the worker_cleanup_period is much shorter period than the timeout and
        # the cleanup is done _several_ times during the run() call.
        self._last_worker_cleanup = 0.0

        while True:
            now = start_time if now is None else time.time()

            if not now - start_time < timeout:
                break

            self._cleanup_workers(now)

            worker_count = len(self._tracked_workers)
            if worker_count >= self.max_workers:
                self.log.debug("Worker count on a limit %s", worker_count)
                time.sleep(1)
                continue

            # We can allocate some workers, if there's something to do.
            try:
                task = self.tasks.pop_task()
            except KeyError:
                # Empty queue!
                if worker_count:
                    # It still makes sense to cycle to finish the workers.
                    self.log.debug("No more tasks, waiting for workers")
                    time.sleep(1)
                    continue
                # Optimization part, nobody is working now, and there's nothing
                # to do.  Just simply wait till the end of the cycle.
                break

            break_on_limit = False
            for limit in self._limits:
                # just skip this task, it will be processed in the next
                # run because we keep re-filling the queue
                if not limit.check(task):
                    self.log.debug("Task '%s' skipped, limit info: %s",
                                   task.id, limit.info())
                    break_on_limit = True
                    break
            if break_on_limit:
                continue

            self._start_worker(task, now)

        self.log.debug("Reaped %s processes", self._clean_daemon_processes())
        self.log.debug("Worker.run() stop at time %s", time.time())

    def _start_worker(self, task, time_now):
        worker_id = self.get_worker_id(repr(task))
        self.redis.hset(worker_id, 'allocated', time_now)
        self._tracked_workers.add(worker_id)
        self.log.info("Starting worker %s, task.priority=%s", worker_id,
                      task.priority)
        self._calculate_limits_for_task(worker_id, task)
        self.start_task(worker_id, task)

    def clean_tasks(self):
        """
        Remove all tasks from queue.
        """
        self.tasks = JobQueue()
        for limit in self._limits:
            limit.clear()

    def _delete_worker(self, worker_id):
        self.redis.delete(worker_id)
        self._tracked_workers.discard(worker_id)

    def _cleanup_workers(self, now):
        """
        Go through all the tracked workers and check if they already finished,
        failed to start or died in the background.
        """

        # This method is called very frequently (several hundreds per second,
        # for each of the attempts to start a worker in the self.run() method).
        # Because the likelihood that some of the background workers changed
        # state is pretty low, we control the frequency of the cleanup here.
        now = time.time()
        if now - self._last_worker_cleanup < self.worker_cleanup_period:
            return

        self.log.debug("Trying to clean old workers")
        self._last_worker_cleanup = time.time()

        for worker_id in self.worker_ids():
            info = self.redis.hgetall(worker_id)

            allocated = info.get('allocated', None)
            if not allocated:
                # In worker manager, we _always_ add 'allocated' tag when we
                # start worker.  So this may only happen when worker is
                # orphaned for some reason (we gave up with him), and it still
                # touches the database on background.
                self.log.info("Missing 'allocated' flag for worker %s", worker_id)
                self._delete_worker(worker_id)
                continue

            allocated = float(allocated)

            if self.has_worker_ended(worker_id, info):
                # finished worker
                self.log.info("Finished worker %s", worker_id)
                self.finish_task(worker_id, info)
                self._delete_worker(worker_id)
                continue

            if info.get('delete'):
                self.log.warning("worker %s deleted", worker_id)
                self._delete_worker(worker_id)
                continue

            if not self.has_worker_started(worker_id, info):
                if now - allocated > self.worker_timeout_start:
                    # This worker failed to start?
                    self.log.error("worker %s failed to start", worker_id)
                    self._delete_worker(worker_id)
                continue

            checked = info.get('checked', allocated)

            if now - float(checked) > self.worker_timeout_deadcheck:
                self.log.info("checking worker %s", worker_id)
                self.redis.hset(worker_id, 'checked', now)
                if self.is_worker_alive(worker_id, info):
                    continue
                self.log.error("dead worker %s", worker_id)

                # The worker could finish in the meantime, make sure we
                # hgetall() once more.
                self.redis.hset(worker_id, 'delete', 1)

    def start_daemon_on_background(self, command, env=None):
        """
        The daemon.DaemonContext() is pretty slow thing, it may take up to 1s
        to finish and return the exit status to the parent process.  But if the
        calling logic is properly prepared for potential startup failures, we
        don't have to wait at all and we can start the background process on
        background, too.  Typical work-around for starting the
        'copr-backend-process-*' scripts that are based on the
        BackgroundWorker.process() logic.
        """
        # pylint: disable=consider-using-with
        process = subprocess.Popen(command, env=env)
        self.log.debug("background pid=%s started (%s)", process.pid, command)

    def _clean_daemon_processes(self):
        """
        Wait for all the finished subprocesses to avoid the leftover zombies.
        Return the number of successfully waited processes.  Complements the
        start_daemon_on_background() above, but called automatically.
        """
        counter = 0
        try:
            # Wait for any background process (pid=-1), and no additional
            # options are needed (options=0).  All the background processes
            # should quit relatively fast (within one second).
            while True:
                (pid, _) = os.waitpid(-1, 0)
                self.log.debug("Worker Manager waited for pid=%s", pid)
                counter += 1
        except ChildProcessError:
            pass
        return counter
