" test worker_manager.py "

import os
import sys
import copy
import time
import logging
from unittest.mock import MagicMock, patch

import pytest
from munch import Munch
from copr_common.enums import DefaultActionPriorityEnum

from copr_common.redis_helpers import get_redis_connection
from copr_common.worker_manager import (
    JobQueue,
    WorkerManager,
    PredicateWorkerLimit,
)
from copr_backend.actions import ActionWorkerManager, ActionQueueTask, Action
from copr_backend.worker_manager import BackendQueueTask

WORKDIR = os.path.dirname(__file__)

REDIS_OPTS = Munch(
    redis_db=9,
    redis_port=7777,
)

log = logging.getLogger()
log.setLevel(logging.DEBUG)

# pylint: disable=too-many-instance-attributes,protected-access


class ToyWorkerManager(WorkerManager):
    # pylint: disable=abstract-method
    process_counter = 0
    task_sleep = 0
    started_in_cycle = 0
    expected_terminations_in_cycle = None

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

        start = time.time()
        #subprocess.check_call(list(map(str, cmd)), env=environ)
        retyped_cmd = list(map(str, cmd))
        self.start_daemon_on_background(retyped_cmd, env=environ)
        self.log.debug("starting-on-background-took %s (%s)",
                       time.time() - start, retyped_cmd)
        self.started_in_cycle += 1

    def _clean_daemon_processes(self):
        """
        Check that we are not leaving any zombies behind us
        """
        waited = super()._clean_daemon_processes()
        self.log.debug("cleaned up %s, started %s", waited, self.started_in_cycle)
        if waited != self.started_in_cycle:
            if self.expected_terminations_in_cycle is not None:
                assert self.expected_terminations_in_cycle == waited
                return waited
            assert False
        return waited

    def run(self, *args, **kwargs):
        self.started_in_cycle = 0
        return super().run(*args, **kwargs)

    def finish_task(self, _w_id, _tinfo):
        pass


class ToyActionWorkerManager(ToyWorkerManager, ActionWorkerManager):
    pass


class ToyQueueTask(BackendQueueTask):
    def __init__(self, _id):
        self._id = _id

    @property
    def id(self):
        return self._id

    @property
    def is_odd(self):
        """ return True if the self.id is odd number """
        return bool(int(self.id) % 2)


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


class BaseTestWorkerManager:
    redis = None
    worker_manager = None

    def setup_method(self, method):
        log.setLevel(logging.DEBUG)
        self.setup_redis()
        self.setup_worker_manager()
        self.setup_tasks()

    def setup_redis(self):
        self.redis = get_redis_connection(REDIS_OPTS)
        self.redis.flushall()

    def setup_worker_manager(self):
        self.worker_manager = ToyWorkerManager(
            redis_connection=self.redis,
            max_workers=5,
            log=log)

    def setup_tasks(self, exclude=None):
        """ Fill the task list """
        if exclude is None:
            exclude = []
        raw_actions = [0, 1, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9]
        actions = [ToyQueueTask(action) for action in raw_actions
                   if not action in exclude]
        self.worker_manager.clean_tasks()
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


class TestLimitedWorkerManager(BaseTestWorkerManager):
    limits = []
    def setup_worker_manager(self):
        self.limits = [
            PredicateWorkerLimit(lambda x: x.is_odd, 3, name="odd"),
            PredicateWorkerLimit(lambda x: not x.is_odd, 2, name="even"),
        ]
        self.worker_manager = ToyWorkerManager(
            redis_connection=self.redis,
            max_workers=50,
            log=log,
            limits=self.limits)

    @patch('copr_common.worker_manager.time.sleep')
    @patch('copr_common.worker_manager.time.time')
    def test_that_limits_are_respected(self, mc_time, _mc_sleep, caplog):
        # each time.time() call incremented by 1
        self.worker_manager.task_sleep = 5
        self.worker_manager.worker_timeout_start = 1000
        mc_time.side_effect = range(1000)
        self.worker_manager.run(timeout=150)
        messages = [
            "Task '4' skipped, limit info: 'even', "
            "matching: worker:0, worker:2",
            "Task '6' skipped, limit info: 'even', "
            "matching: worker:0, worker:2",
            "Task '7' skipped, limit info: 'odd', "
            "matching: worker:1, worker:3, worker:5",
            "Task '8' skipped, limit info: 'even', "
            "matching: worker:0, worker:2",
            "Task '9' skipped, limit info: 'odd', "
            "matching: worker:1, worker:3, worker:5",
        ]
        for msg in messages:
            assert ('root', logging.DEBUG, msg) in caplog.record_tuples

        # Even though the "even" limit kicked-out task 4, the task 5 is still
        # successfully started because that's the third "odd" task.  The rest of
        # tasks is just skipped.
        assert ('root', logging.INFO,
                "Starting worker worker:5, task.priority=0") in \
            caplog.record_tuples

        # finish the task now
        self.redis.hset("worker:5", "status", "0")

        self.setup_tasks()  # re-calculate limits
        self.worker_manager.run(timeout=150)

        # check worker manager recognized the finished task
        assert ('root', logging.INFO, "Finished worker worker:5") \
                in caplog.record_tuples

        # worker 7 is not yet started, it waits for next run() because run()
        # doesn't free the limit quota when removing worker from Redis (see
        # issue #1415)
        worker_7_started = "Starting worker worker:7, task.priority=0"
        assert ('root', logging.INFO, worker_7_started) not in \
            caplog.record_tuples

        # another run finally takes the task 7, because 5 is done
        self.setup_tasks(exclude=[5])
        self.worker_manager.run(timeout=150)
        assert ('root', logging.INFO, worker_7_started) in \
            caplog.record_tuples


class TestWorkerManager(BaseTestWorkerManager):
    def test_worker_starts(self):
        task = self.worker_manager.tasks.pop_task()
        assert task.id == 0
        self.worker_manager._start_worker(task, time.time())
        worker_id = self.worker_manager.get_worker_id(repr(task))
        assert len(self.redis.keys(worker_id)) == 1
        self.worker_manager._clean_daemon_processes()

    def test_number_of_tasks(self):
        assert self.remaining_tasks() == 10

    def test_task_to_worker_id(self):
        wid = "{}:123".format(self.worker_manager.worker_prefix)
        assert self.worker_manager.get_task_id_from_worker_id(wid) == "123"

    @patch('copr_common.worker_manager.time.sleep')
    def test_preexisting_broken_worker(self, _mc_sleep, caplog):
        """ from previous systemctl restart """
        fake_worker_name = self.worker_manager.worker_prefix + ":fake"
        self.redis.hset(fake_worker_name, "foo", "bar")
        self.worker_manager.run(timeout=0.0001)
        msg = "Missing 'allocated' flag for worker " + fake_worker_name
        assert ('root', logging.INFO, msg) in caplog.record_tuples

    def test_cancel_task(self):
        self.redis.hset('worker:4', 'allocated', 1)
        self.worker_manager.cancel_task_id(3)
        self.worker_manager.cancel_task_id(4)
        self.worker_manager.cancel_task_id(666)
        assert self.redis.hgetall('worker:3') == {}
        assert "cancel_request" in self.redis.hgetall('worker:4')

    def test_slow_priority_queue_filling(self):
        """
        We discovered that adding tasks to a priority queue was a bottleneck
        when having a large (70k+ builds) queue, see #2095. Make sure this never
        happen again.
        """
        tasks = [ToyQueueTask(i) for i in range(100000)]

        # We need to run this test with logging only INFO, otherwise we waste
        # around 5 seconds just on running self.log.debug because we need to
        # connect to redis for each call
        # The point of this test is to make sure that adding tasks to priority
        # queue is not a bottleneck on production, and we don't use DEBUG there
        # anyway.
        log.setLevel(logging.INFO)

        t1 = time.time()
        for task in tasks:
            self.worker_manager.add_task(task)
        t2 = time.time()

        # It should actually be faster than 1 second but I am adding one to
        # prevent false alarms in case somebody has a slow machine
        assert t2 - t1 < 2


def wait_pid_exit(pid):
    """ wait till pid stops responding to no-op kill 0 """
    while True:
        try:
            os.kill(int(pid), 0)
        except OSError:
            return True
        time.sleep(0.1)


class TestActionWorkerManager(BaseTestWorkerManager):
    # pylint: disable=attribute-defined-outside-init
    def setup_worker_manager(self):
        self.worker_manager = ToyActionWorkerManager(
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

    def setup_tasks(self, exclude=None):
        if exclude is None:
            exclude = []
        raw_actions = [x for x in [0, 1, 2, 3, 3, 3, 4, 5, 6, 7, 8, 9]
                       if x not in exclude]
        self.worker_manager.clean_tasks()
        for action in raw_actions:
            action = ToyQueueTask(action)
            self.worker_manager.add_task(action)

    def test_run_starts_the_workers(self):
        self.worker_manager.run(timeout=0.0001)
        workers = self.workers()
        assert len(workers) == 1
        assert workers[0] == self.w0

        args = self.wait_field(self.w0, 'status')
        assert 'status' in args
        assert 'PID' in args
        assert 'started' in args

        self.worker_manager.run(timeout=0.0001)

        keys = self.workers()
        assert self.w0 not in keys
        # we are not sure 'toy:1' had a chance to start
        assert len(keys) <= 1

    def test_delete_not_allocated_workers(self):
        self.worker_manager.run(timeout=0.0001)
        assert self.w0 in self.workers()
        # "allocated" can be the only one hash attribute, so add another one to
        # not loose the key from redis DB
        self.redis.hset(self.w0, "keep_me_around", "yes?")
        self.redis.hdel(self.w0, "allocated")
        self.worker_manager.run(timeout=0.0001)
        params = self.redis.hgetall(self.w0)
        if params:
            # The action-processor.py script re-added itself to the database,
            # but still the 'keep_me_around' flag disappeared after worker
            # manager removed it.
            assert "keep_me_around" not in params

    def test_delete_not_started_workers(self):
        self.worker_manager.environ = {'FAIL_EARLY': '1'}
        self.worker_manager.worker_timeout_start = 0
        self.worker_manager.run(timeout=0.0001)
        assert self.workers() == [self.w0]
        self.worker_manager.run(timeout=0.0001)
        # toy 0 is deleted now
        assert self.workers() == [self.w1]

    def wait_field(self, worker, field):
        for _ in range(0, 100):
            time.sleep(0.25)
            params = self.redis.hgetall(self.w0)
            if field in params:
                return params
        raise Exception("Unsuccessful wait for {} in {}".format(worker, field))

    @pytest.mark.parametrize('fail', ['FAIL_STARTED_PID', 'FAIL_STARTED'])
    @patch('copr_common.worker_manager.time.time')
    def test_delete_not_finished_workers(self, mc_time, fail):
        self.worker_manager.environ = {fail: '1'}
        self.worker_manager.worker_timeout_deadcheck = 0.4

        # each time.time() call incremented by 1
        mc_time.side_effect = range(1000)

        # first loop just starts the toy:0 worker
        with patch('copr_common.worker_manager.time.sleep'):
            self.worker_manager.run(timeout=1)

        params = self.wait_field(self.w0, 'started')
        assert self.w0 in self.workers()
        assert 'started' in params

        if fail == 'FAIL_STARTED':
            # make sure kernel cleans up the process, so the next wm.run()
            # certainly sets the 'delete' flag
            wait_pid_exit(params['PID'])

        # toy 0 is marked for deleting
        with patch('copr_common.worker_manager.time.sleep'):
            self.worker_manager.run(timeout=1)
        assert 'delete' in self.redis.hgetall(self.w0)

        # toy 0 should be deleted
        with patch('copr_common.worker_manager.time.sleep'):
            self.worker_manager.run(timeout=1)
        keys = self.workers()
        assert self.w1 in keys
        assert self.w0 not in keys

    def test_all_passed(self, caplog):
        # It is a lot of fun with Popen().  It seems it has some zombie reaping
        # mechanism.  If the calling function objects are destroyed (including
        # the Popen() return value reference), the future call to Popen() seems
        # to just reap the old Popen() processes.
        self.worker_manager.expected_terminations_in_cycle = 5

        self.worker_manager.run(timeout=100)
        for i in range(0, 10):
            smsg = "Starting worker {}{}, task.priority=0"
            assert ('root', 20, smsg.format(self.wprefix, i)) in \
                caplog.record_tuples
            assert ('root', 20, 'Finished worker {}{}'.format(self.wprefix, i)) in caplog.record_tuples

    def test_add_task_for_running_worker(self, caplog):
        # at least 'toy:0' should be reeady
        self.worker_manager.run(timeout=0.0001)

        queue = copy.deepcopy(self.worker_manager.tasks)
        self.worker_manager.add_task(ToyQueueTask(0))
        assert len(queue.prio_queue) == len(self.worker_manager.tasks.prio_queue)
        assert ('root', logging.DEBUG,
                "Task 0 already has a worker process") in caplog.record_tuples

    def test_empty_queue_but_workers_running(self):
        'check that sleep(1) is done if queue is empty, but some workers exist'

        self.worker_manager.clean_tasks()

        # only one task, but it will take some time.
        self.worker_manager.task_sleep = 0.5
        self.worker_manager.add_task(ToyQueueTask(0))

        # start the worker
        self.worker_manager.run(timeout=0.0001) # start them task

        with patch('copr_common.worker_manager.time.sleep') as sleep:
            # we can spawn more workers, but queue is empty
            self.worker_manager.run(timeout=0.0001)
            assert sleep.called
        assert len(self.worker_manager.worker_ids()) == 1

        # let the task finish
        self.wait_field(self.w0, 'status')

        # check that we don't sleep here (no worker, no task)
        with patch('copr_common.worker_manager.time.sleep') as sleep:
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
        self.worker_manager.add_task(ToyQueueTask(0))
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

    def test_max_workers_has_effect(self):
        self.worker_manager.max_workers = 1
        self.worker_manager.run(timeout=1)
        assert self.w0 in self.workers()
        assert self.w1 not in self.workers()


class TestActionWorkerManagerPriorities(BaseTestWorkerManager):
    def setup_worker_manager(self):
        self.worker_manager = ToyActionWorkerManager(
            redis_connection=self.redis,
            max_workers=5,
            log=log)

    def setup_tasks(self, exclude=None):
        _unused = (self, exclude)

    def pop(self):
        return self.worker_manager.tasks.pop_task()

    def test_actions_priorities(self):
        frontend_data = [
            {"id": 10, "priority": DefaultActionPriorityEnum("delete")},
            {"id": 11, "priority": DefaultActionPriorityEnum("delete")},
            {"id": 12, "priority": DefaultActionPriorityEnum("createrepo")},
            {"id": 13, "priority": DefaultActionPriorityEnum("update_comps")},
            {"id": 14, "priority": DefaultActionPriorityEnum("rawhide_to_release")},
            {"id": 15, "priority": DefaultActionPriorityEnum("rawhide_to_release")},
            {"id": 16, "priority": DefaultActionPriorityEnum("build_module")},
            {"id": 17, "priority": DefaultActionPriorityEnum("cancel_build")},
            {"id": 18, "priority": DefaultActionPriorityEnum("fork")},
            {"id": 19, "priority": DefaultActionPriorityEnum("gen_gpg_key")},
            {"id": 20, "priority": 0},
        ]
        for action in frontend_data:
            queue_task = ActionQueueTask(Action(MagicMock(), action, log=log))
            self.worker_manager.add_task(queue_task)

        assert self.pop().id == 19
        assert self.pop().id == 17

        # These have the same priority and the queue is FIFO
        assert self.pop().id == 12
        assert self.pop().id == 13
        assert self.pop().id == 16
        assert self.pop().id == 18
        assert self.pop().id == 20

        assert self.pop().id == 10
        assert self.pop().id == 11

        assert self.pop().id == 14
        assert self.pop().id == 15

        # Tasks queue is empty now
        with pytest.raises(KeyError) as ex:
            self.pop()
        assert "empty" in str(ex)

    def test_backend_priority_adjustments(self):
        """
        Test that backend still can adjust or ultimately override priorities
        """
        frontend_data = [
            {"id": 10, "priority": DefaultActionPriorityEnum("delete")},
            {"id": 11, "priority": DefaultActionPriorityEnum("delete")},
            {"id": 12, "priority": DefaultActionPriorityEnum("createrepo")},
            {"id": 13, "priority": DefaultActionPriorityEnum("gen_gpg_key")},
            {"id": 14, "priority": DefaultActionPriorityEnum("fork")},
        ]
        actions = [ActionQueueTask(Action(MagicMock(), action, log)) for action in frontend_data]

        # QueueTask.backend_priority is a property which should be
        # overriden when in the class descendants.
        delattr(BackendQueueTask, "backend_priority")
        actions[0].backend_priority = 0
        actions[1].backend_priority = -999
        actions[2].backend_priority = 999
        actions[3].backend_priority = 0
        actions[4].backend_priority = -900

        for action in actions:
            self.worker_manager.add_task(action)

        assert self.pop().id == 11
        assert self.pop().id == 14
        assert self.pop().id == 13
        assert self.pop().id == 10
        assert self.pop().id == 12
