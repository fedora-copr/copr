import time
from heapq import heappop, heappush
import itertools
import redis
import logging

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
        entry = self.entry_finder.pop(repr(task))
        entry[-1] = self.removed

    def pop_task(self):
        'Remove and return the lowest priority task. Raise KeyError if empty.'
        while self.prio_queue:
            priority, count, task = heappop(self.prio_queue)
            if task is not self.removed:
                del self.entry_finder[repr(task)]
                return task
        raise KeyError('pop from an empty priority queue')


class QueueTask:
    def __repr__(self):
        return str(self.id)

    @property
    def id(self):
        raise NotImplementedError

    @property
    def priority(self):
        return sum([self.frontend_priority, self.backend_priority])

    @property
    def frontend_priority(self):
        return 0

    @property
    def backend_priority(self):
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
    """
    worker_prefix = 'worker' # make sure this is unique in each class
    worker_timeout_start = 30
    worker_timeout_deadcheck = 60

    def __init__(self, redis_connection=None, max_workers=8, log=None):
        self.tasks = JobQueue()
        self.log = log if log else logging.getLogger()
        self.redis = redis_connection
        self.max_workers = max_workers

    def start_task(self, worker_id, task):
        """
        Start background job using the 'task' object taken from the 'tasks'
        queue.  The background task should _on its own_ and ASAP let the manager
        know that it successfully started (e.g. mark the job 'started' in redis
        DB), so the has_worker_started() method later gives us valid info.
        """
        raise NotImplementedError

    def finish_task(self, worker_id, task):
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
        return 'started' in task_info

    def has_worker_ended(self, worker_id, task_info):
        """
        Check 'task_info' (dictionary output from redis) whether the task is
        already finished by worker.  If yes, do whatever is needed with the
        result (contact frontend) and return True.  If the task is still
        processed, return False.
        """
        raise NotImplementedError

    def is_worker_alive(self, worker_id, task_info):
        """
        Check staled jobs on background, whether they haven't died before they
        notified us about the status.  We'll keep asking after
        worker_timeout_deadcheck seconds left since we tried to spawn the
        worker.
        """
        raise NotImplementedError

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

    def has_worker(self, task_id):
        worker_id = self.get_worker_id(task_id)
        return worker_id in self.worker_ids()

    def add_task(self, task):
        task_id = repr(task)
        if self.has_worker(task_id):
            # No need to re-add this to queue.
            self.log.warning("Task %s has worker, skipped", task_id)
            return

        self.log.info("Adding task %s to queue", task_id)
        self.tasks.add_task(task, task.priority)

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

        while True:
            now = start_time if now is None else time.time()

            if not now - start_time < timeout:
                break

            self._cleanup_workers(now)

            worker_count = len(self.worker_ids())
            if worker_count >= self.max_workers:
                time.sleep(1)
                continue

            # We can allocate some workers, if there's something to do.
            try:
                task = self.tasks.pop_task()
            except KeyError:
                # Empty queue!
                if worker_count:
                    # It still makes sense to cycle to finish the workers.
                    time.sleep(1)
                    continue
                # Optimization part, nobody is working now, and there's nothing
                # to do.  Just simply wait till the end of the cycle.
                break

            self._start_worker(task, now)

    def _start_worker(self, task, time_now):
        worker_id = self.get_worker_id(repr(task))
        self.redis.hset(worker_id, 'allocated', time_now)
        self.log.info("Starting worker %s", worker_id)
        self.start_task(worker_id, task)

    def clean_tasks(self):
        'remove all tasks from queue'
        self.tasks = JobQueue()

    def _cleanup_workers(self, now):
        for worker_id in self.worker_ids():
            info = self.redis.hgetall(worker_id)

            allocated = info.get('allocated', None)
            if not allocated:
                # In worker manager, we _always_ add 'allocated' tag when we
                # start worker.  So this may only happen when worker is
                # orphaned for some reason (we gave up with him), and it still
                # touches the database on background.
                self.log.info("Missing 'allocated' flag for worker %s", worker_id)
                self.redis.delete(worker_id)
                continue

            allocated = float(allocated)

            if self.has_worker_ended(worker_id, info):
                # finished worker
                self.log.info("Finished worker %s", worker_id)
                self.finish_task(worker_id, info)
                self.redis.delete(worker_id)
                continue

            if info.get('delete'):
                self.log.warning("worker %s deleted", worker_id)
                self.redis.delete(worker_id)
                continue

            if not self.has_worker_started(worker_id, info):
                if now - allocated > self.worker_timeout_start:
                    # This worker failed to start?
                    self.log.error("worker %s failed to start", worker_id)
                    self.redis.delete(worker_id)
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
