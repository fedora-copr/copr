" test worker_manager.py "

import os
import sys
import copy
import time
import logging
import subprocess
from unittest.mock import MagicMock, patch
from munch import Munch

WORKDIR = os.path.dirname(__file__)

from backend.helpers import get_redis_connection
from backend.actions import ActionWorkerManager, ActionQueueTask
from backend.worker_manager import JobQueue

REDIS_OPTS = Munch(
    redis_db=9,
    redis_port=7777,
)

log = logging.getLogger()
log.setLevel(logging.DEBUG)


class ToyWorkerManager(ActionWorkerManager):
    process_counter = 0
    task_sleep = 0

    def start_task(self, worker_id, task):
        self.process_counter += 1

        cmd = [
            'python3',
            os.path.join(WORKDIR, 'action-processor.py'),
            self.process_counter,
            repr(task),
            worker_id,
            self.task_sleep,
        ]

        environ = {} # os.environ.copy()
        task_env = getattr(self, 'environ', None)
        if task_env:
           environ.update(task_env)

        subprocess.check_call(list(map(str, cmd)), env=environ)


class TestPrioQueue(object):
    def setup_method(self, method):
        raw_actions = [0, 1, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9]
        self.queue = JobQueue()
        for action in raw_actions:
            self.queue.add_task(action, priority=10)

        # one task re-added with priority
        self.queue.add_task(7, priority=5)

    def get_tasks(self):
        tasks = []
        while True:
            try:
                tasks += [self.queue.pop_task()]
            except:
                break
        return tasks

    def test_queue_order(self):
        assert self.get_tasks() == [7, 0, 1, 2, 3, 4, 5, 6, 8, 9]

    def test_pop_push(self):
        self.queue.pop_task()
        self.queue.add_task(11) # prio 0 by default
        assert self.get_tasks() == [11, 0, 1, 2, 3, 4, 5, 6, 8, 9]

    def test_push_back(self):
        self.queue.pop_task()
        self.queue.pop_task()
        self.queue.add_task(10, priority=10) # put back
        assert self.get_tasks() == [1, 2, 3, 4, 5, 6, 8, 9, 10]

    def test_shift_prio(self):
        self.queue.add_task(9, priority=5) # move front, but after 7
        self.queue.add_task(6) # move forward
        assert self.get_tasks() == [6, 7, 9, 0, 1, 2, 3, 4, 5, 8]


class TestWorkerManager(object):
    redis = None
    worker_manager = None

    def setup_method(self, method):
        self.redis = get_redis_connection(REDIS_OPTS)
        self.redis.flushall()

        self.worker_manager = ToyWorkerManager(
            redis_connection=self.redis,
            max_workers=5,
            log=log)

        prefix = 'toy:' + str(time.time())
        self.worker_manager.worker_prefix = prefix
        prefix += ':'
        self.wprefix = prefix
        self.w0 = prefix + '0'
        self.w1 = prefix + '1'

        self.worker_manager.frontend_client = MagicMock()

        raw_actions = [0, 1, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9]
        actions = [ActionQueueTask(action) for action in raw_actions]
        for action in actions:
            self.worker_manager.add_task(action)

    def workers(self):
        return self.worker_manager.worker_ids()

    def remaining_tasks(self):
        count = 0
        while True:
            try:
                self.worker_manager.tasks.pop_task()
                count += 1
            except:
                break
        return count

    def test_worker_starts(self):
        task = self.worker_manager.tasks.pop_task()
        assert task.id == 0
        self.worker_manager._start_worker(task)
        worker_id = self.worker_manager.get_worker_id(repr(task))
        assert len(self.redis.keys(worker_id)) == 1

    def test_number_of_tasks(self):
        assert self.remaining_tasks() == 10

    def test_run_starts_the_workers(self):
        self.worker_manager.run(timeout=0.0001)
        workers = self.workers()
        assert len(workers) == 1
        assert workers[0] == self.w0

        args = self.wait_field(self.w0, 'started')
        assert 'status' in args
        assert 'PID' in args
        assert 'started' in args

        self.worker_manager.run(timeout=0.0001)

        keys = self.workers()
        assert self.w0 not in keys
        # we are not sure 'toy:1' had a chance to start
        assert len(keys) <= 1

    def test_delete_not_started_workers(self):
        self.worker_manager.environ = {'FAIL_EARLY': '1'}
        self.worker_manager.worker_timeout_start = 0
        self.worker_manager.run(timeout=0.0001)
        assert self.workers() == [self.w0]
        self.worker_manager.run(timeout=0.0001)
        # toy 0 is deleted now
        assert self.workers() == [self.w1]

    def wait_field(self, worker, field):
        for _ in range(0, 10):
            time.sleep(0.25)
            params = self.redis.hgetall(self.w0)
            if field in params:
                return params
        return params

    def test_delete_not_finished_workers(self):
        self.worker_manager.environ = {'FAIL_STARTED': '1'}
        self.worker_manager.worker_timeout_deadcheck = 0.4

        # start toy:0
        self.worker_manager.run(timeout=0.0001)

        params = self.wait_field(self.w0, 'started')
        assert self.w0 in self.workers()
        assert 'started' in params

        # toy 0 is marked for deleting
        self.worker_manager.run(timeout=0.0001)
        assert 'delete' in self.redis.hgetall(self.w0)

        # toy 0 should be deleted
        self.worker_manager.run(timeout=0.0001)
        keys = self.workers()
        assert self.w1 in keys
        assert self.w0 not in keys

    def test_all_passed(self, caplog):
        self.worker_manager.run(timeout=100)
        for i in range(0, 10):
            assert ('root', 20, 'Starting worker {}{}'.format(self.wprefix, i)) in caplog.record_tuples
            assert ('root', 20, 'Finished worker {}{}'.format(self.wprefix, i)) in caplog.record_tuples

    def test_add_task_for_running_worker(self, caplog):
        # at least 'toy:0' should be reeady
        self.worker_manager.run(timeout=0.0001)

        queue = copy.deepcopy(self.worker_manager.tasks)
        self.worker_manager.add_task(ActionQueueTask(0))
        assert len(queue.prio_queue) == len(self.worker_manager.tasks.prio_queue)
        assert ('root', logging.WARNING, "Task 0 has worker, skipped") in caplog.record_tuples

    def test_empty_queue_but_workers_running(self):
        'check that sleep(1) is done if queue is empty, but some workers exist'

        self.worker_manager.clean_tasks()

        # only one task, but it will take some time.
        self.worker_manager.task_sleep = 0.5
        self.worker_manager.add_task(ActionQueueTask(0))

        # start the worker
        self.worker_manager.run(timeout=0.0001) # start them task

        with patch('backend.worker_manager.time.sleep') as sleep:
            # we can spawn more workers, but queue is empty
            self.worker_manager.run(timeout=0.0001)
            assert sleep.called
        assert len(self.worker_manager.worker_ids()) == 1

        # let the task finish
        self.wait_field(self.w0, 'status')

        # check that we don't sleep here (no worker, no task)
        with patch('backend.worker_manager.time.sleep') as sleep:
            self.worker_manager.run(timeout=0.0001)
            assert not sleep.called

        assert len(self.worker_manager.worker_ids()) == 0

    def test_that_we_check_aliveness(self):
        """
        Worker Manager checks whether worker is running each 'worker_timeout_deadcheck'
        period, check whether it works
        """
        self.worker_manager.task_sleep = 3 # assure task takes some time
        self.worker_manager.clean_tasks()
        self.worker_manager.add_task(ActionQueueTask(0))
        self.worker_manager.worker_timeout_start = 1
        self.worker_manager.worker_timeout_deadcheck = 1.5

        # start the worker
        self.worker_manager.run(timeout=0.0001)

        # let the task start
        self.wait_field(self.w0, 'PID')

        # timeout for liveness check not yet left
        self.worker_manager.run(timeout=0.0001)
        params = self.redis.hgetall(self.w0)
        if 'checked' in params:
            # slow builder, the delay between previous two run() calls were so
            # long so the second one managed to even check whether the worker is
            # alive.  So if that happened, the delay needs to be larger than
            # deadcheck at least.
            checked = float(params['checked'])
            started = float(params['allocated'])
            assert started + self.worker_manager.worker_timeout_deadcheck <= checked

        # time for check..
        time.sleep(1.5)
        self.worker_manager.run(timeout=0.0001)
        params = self.redis.hgetall(self.w0)
        assert 'checked' in params

        # let the task finish
        self.wait_field(self.w0, 'status')
        self.worker_manager.run(timeout=0.0001)

        assert len(self.worker_manager.worker_ids()) == 0
