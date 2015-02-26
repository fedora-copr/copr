import os
import tempfile
import shutil
import time

from bunch import Bunch
import pytest
import retask
from retask import ConnectionError
import six
import sys

from backend.daemons.backend import CoprBackend, run_backend
from backend.exceptions import CoprBackendError

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


STDOUT = "stdout"
STDERR = "stderr"
COPR_OWNER = "copr_owner"
COPR_NAME = "copr_name"
COPR_VENDOR = "vendor"

MODULE_REF = "backend.daemons.backend"

@pytest.yield_fixture
def mc_rt_queue():
    with mock.patch("{}.Queue".format(MODULE_REF)) as mc_queue:
        yield mc_queue

@pytest.yield_fixture
def mc_worker():
    with mock.patch("{}.Worker".format(MODULE_REF)) as worker:
        yield worker

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as time_:
        yield time_

@pytest.yield_fixture
def mc_be():
    with mock.patch("{}.CoprBackend".format(MODULE_REF)) as obj:
        yield obj

@pytest.yield_fixture
def mc_daemon_context():
    with mock.patch("{}.DaemonContext".format(MODULE_REF)) as obj:
        yield obj




class TestBackend(object):

    def setup_method(self, method):
        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

        self.bc_patcher = mock.patch("backend.daemons.backend.BackendConfigReader")
        self.bc = self.bc_patcher.start()

        self.mp_patcher = mock.patch("backend.daemons.backend.multiprocessing")
        self.mc_mp = self.mp_patcher.start()

        self.worker_logdir = os.path.join(self.tmp_dir_path, "workers")
        self.config_file = "/dev/null/copr.conf"
        self.ext_opts = {}

        # effective config options
        self.bc_obj = MagicMock()

        self.opts = Bunch(
            worker_logdir=self.worker_logdir,
            build_groups=[
                {
                    "id": 0,
                    "name": "PC",
                    "archs": ["i386", "x86_64"],
                    "max_workers": 2
                },
                {
                    "id": 1,
                    "name": "ARM",
                    "archs": ["armv7"],
                    "max_workers": 3
                },
            ],
            exit_on_worker=False,
            sleeptime=1,
            frontend_url="http://example.com/backend",
            frontend_base_url="http://example.com",
            frontend_auth="foobar",


        )
        self.bc_obj.read.return_value = self.opts
        self.bc.return_value = self.bc_obj

        # for run backend
        self.pidfile_path = os.path.join(self.tmp_dir_path, "backend.pid")
        self.grp_patcher = mock.patch("backend.daemons.backend.grp")
        self.pwd_patcher = mock.patch("backend.daemons.backend.pwd")
        self.grp = self.grp_patcher.start()
        self.pwd = self.pwd_patcher.start()

        self.run_opts = Bunch(
            daemonize=True,
            pidfile=self.pidfile_path,
            config_file=self.config_file,
        )


    @pytest.fixture
    def init_be(self):
        self.be = CoprBackend(self.config_file, self.ext_opts)


    @pytest.yield_fixture
    def mc_vmm_stuff(self):
        patchers = []
        for klass_name in ["Spawner", "HealthChecker", "Terminator", "VmManager", "VmMaster"]:
            patcher = mock.patch("{}.{}".format(MODULE_REF, klass_name))
            patchers.append(patcher)
            setattr(self, klass_name, patcher.start())

        yield None
        for patcher in patchers:
            patcher.stop()

    def teardown_method(self, method):
        # print("\nremove: {}".format(self.tmp_dir_path))
        shutil.rmtree(self.tmp_dir_path)
        self.bc_patcher.stop()
        self.grp_patcher.stop()
        self.pwd_patcher.stop()

    def test_constructor_no_config(self):
        with pytest.raises(CoprBackendError):
            self.be = CoprBackend(None, self.ext_opts)

    def test_constructor(self):

        assert not os.path.exists(self.worker_logdir)
        self.init_be()
        assert os.path.exists(self.worker_logdir)
        # import  ipdb; ipdb.set_trace()

        assert self.be.config_reader == self.bc_obj
        assert self.bc_obj.read.called

    def test_clean_task_queue_error(self, init_be):
        mc_queue = MagicMock(length=1)
        mc_queue.dequeue.side_effect = retask.ConnectionError()
        self.be.task_queues[0] = mc_queue

        with pytest.raises(CoprBackendError):
            self.be.clean_task_queues()

    def test_clean_task_queue_ok(self, init_be):
        mc_queue = MagicMock(length=5)
        def decr():
            mc_queue.length -= 1

        mc_queue.dequeue.side_effect = decr
        self.be.task_queues[0] = mc_queue
        self.be.clean_task_queues()

        assert len(mc_queue.dequeue.call_args_list) == 5

    def test_init_task_queues(self, mc_rt_queue, init_be):

        mc_rt_queue.side_effect = lambda name: MagicMock(name=name)
        self.be.clean_task_queues = MagicMock()
        self.be.init_task_queues()

        assert mc_rt_queue.call_args_list == \
               [mock.call("copr-be-0"), mock.call("copr-be-1")]
        assert self.be.task_queues[0].connect.called
        assert self.be.task_queues[1].connect.called

    def test_init_task_queues_error(self, mc_rt_queue, init_be):

        mc_rt_queue.return_value.connect.side_effect = ConnectionError()
        self.be.clean_task_queues = MagicMock()

        with pytest.raises(CoprBackendError):
            self.be.init_task_queues()

    @mock.patch("backend.daemons.backend.CoprBackendLog")
    @mock.patch("backend.daemons.backend.CoprJobGrab")
    def test_dummy_init_sub_process(self, mc_jobgrab, mc_logger, init_be, mc_vmm_stuff):

        self.be.init_sub_process()
        assert mc_logger.called
        assert mc_logger.call_args == mock.call(self.be.opts, self.be.events)
        assert mc_logger.return_value.start.called
        assert mc_jobgrab.called
        assert mc_jobgrab.call_args == mock.call(opts=self.be.opts,
                                                 events=self.be.events,
                                                 frontend_client=self.be.frontend_client,
                                                 lock=self.be.lock)
        assert mc_jobgrab.return_value.start.called

        assert self.VmMaster.called
        assert self.VmMaster.return_value.start.called

    def test_event(self, mc_time, init_be):
        mc_time.time.return_value = self.test_time

        self.be.events = MagicMock()
        self.be.event("foobar")

        self.be.events.put.call_args == mock.call({
            "what": "foobar", "when": self.test_time, "who": "main"
        })

    def test_update_conf(self, init_be):
        test_obj = MagicMock()
        self.bc_obj.read.return_value = test_obj

        self.be.update_conf()
        assert self.bc_obj.read.called
        assert self.be.opts == test_obj

    def test_spin_up_workers_by_group(self, mc_worker, init_be):
        worker = MagicMock()
        mc_worker.return_value = worker

        group = self.opts.build_groups[0]
        self.be.spin_up_workers_by_group(group)

        assert mc_worker.called
        assert len(mc_worker.call_args_list) == group["max_workers"]
        assert worker.start.called
        assert len(worker.start.call_args_list) == group["max_workers"]
        assert len(self.be.workers_by_group_id[0]) == group["max_workers"]

    def test_spin_up_workers_by_group_partial(self, mc_worker, init_be):
        worker = MagicMock()
        mc_worker.return_value = worker

        group = self.opts.build_groups[1]

        self.be.workers_by_group_id[1].append(worker)
        self.be.spin_up_workers_by_group(group)

        assert mc_worker.called
        assert len(mc_worker.call_args_list) == group["max_workers"] - 1
        assert worker.start.called
        assert len(worker.start.call_args_list) == group["max_workers"] - 1
        assert len(self.be.workers_by_group_id[1]) == group["max_workers"]

    def test_prune_dead_workers_by_group(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False


        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.prune_dead_workers_by_group_id(0)

        assert len(self.be.workers_by_group_id) == 1
        assert worker_dead.terminate.called
        assert not worker_alive.terminate.called

    def test_prune_dead_workers_by_group_terminate(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.opts.exit_on_worker = True

        with pytest.raises(CoprBackendError):
            self.be.prune_dead_workers_by_group_id(0)

        assert len(self.be.workers_by_group_id) == 1
        assert worker_dead.terminate.called
        assert not worker_alive.terminate.called

    def test_terminate(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.clean_task_queues = MagicMock()

        self.be.terminate()

        assert self.be.clean_task_queues.called
        assert self.be.abort
        assert worker_alive.terminate_instance.called
        assert worker_dead.terminate_instance.called

    def test_run(self, mc_time, mc_rt_queue, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.clean_task_queues = MagicMock()
        self.be.init_sub_process = MagicMock()
        # self.be.init_task_queues = MagicMock()
        self.be.update_conf = MagicMock()
        self.be.spin_up_workers_by_group = MagicMock()

        def spin_up():
            self.be.workers_by_group_id[0].append(worker_alive)
            self.be.workers_by_group_id[0].append(worker_dead)
            self.be.workers_by_group_id[1].append(worker_alive)
            self.be.workers_by_group_id[1].append(worker_dead)

        self.be.spin_up_workers_by_group = MagicMock()
        self.be.spin_up_workers_by_group.side_effect = lambda foo: spin_up()
        mc_time.sleep.side_effect = lambda foo: self.be.terminate()

        self.be.run()
        assert self.be.spin_up_workers_by_group.call_args_list == [
            mock.call(self.opts.build_groups[0]),
            mock.call(self.opts.build_groups[1]),
        ]
        assert self.be.update_conf.called
        assert self.be.abort
        assert not self.be.workers_by_group_id[0]
        assert not self.be.workers_by_group_id[1]

    def test_run_backend_basic(self, mc_be, mc_daemon_context):
        self.grp.getgrnam.return_value.gr_gid = 7
        self.pwd.getpwnam.return_value.pw_uid = 9

        run_backend(self.run_opts)
        ddc = mc_daemon_context.call_args[1]
        assert ddc["signal_map"] == {1: u'terminate', 15: u'terminate'}
        assert ddc["umask"] == 0o22
        assert ddc["gid"] == 7
        assert ddc["uid"] == 9
        assert ddc["stderr"] == sys.stderr

        assert mc_be.called
        expected_call = mock.call(self.config_file, ext_opts=self.run_opts)
        assert mc_be.call_args == expected_call

    def test_run_backend_keyboard_interrupt(self, mc_be, mc_daemon_context, capsys):
        mc_be.return_value.run.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run_backend(self.run_opts)

        stdout, stderr = capsys.readouterr()
        assert "Killing/Dying" in stderr
