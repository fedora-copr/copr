import multiprocessing
import os

from subprocess import CalledProcessError

from ansible.errors import AnsibleError
from bunch import Bunch
import pytest
import tempfile
import shutil
import time

import six

from backend.constants import BuildStatus
from backend.exceptions import CoprWorkerError, CoprWorkerSpawnFailError, MockRemoteError
from backend.job import BuildJob

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


from backend.daemons.dispatcher import Worker, WorkerCallback

STDOUT = "stdout"
STDERR = "stderr"
COPR_OWNER = "copr_owner"
COPR_NAME = "copr_name"
COPR_VENDOR = "vendor"


class TestDispatcher(object):

    def setup_method(self, method):
        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

        self.pkg_pdn = "foobar"
        self.pkg_name = "{}.src.rpm".format(self.pkg_pdn)
        self.pkg_path = os.path.join(self.tmp_dir_path, self.pkg_name)
        with open(self.pkg_path, "w") as handle:
            handle.write("1")

        self.CHROOT = "fedora-20-x86_64"
        self.vm_ip = "192.168.1.2"
        self.vm_name = "VM_{}".format(self.test_time)

        self.DESTDIR = os.path.join(self.tmp_dir_path, COPR_OWNER, COPR_NAME)
        self.DESTDIR_CHROOT = os.path.join(self.DESTDIR, self.CHROOT)
        self.FRONT_URL = "htt://front.example.com"
        self.BASE_URL = "http://example.com/results"
        self.PKG_NAME = "foobar"
        self.PKG_VERSION = "1.2.3"
        self.HOST = "127.0.0.1"
        self.SRC_PKG_URL = "http://example.com/{}-{}.src.rpm".format(self.PKG_NAME, self.PKG_VERSION)
        self.job_build_id = 12345
        self.task = {
            "project_owner": COPR_OWNER,
            "project_name": COPR_NAME,
            "pkgs": self.SRC_PKG_URL,
            "repos": "",
            "build_id": self.job_build_id,
            "chroot": self.CHROOT,
        }

        self.spawn_pb = "/spawn.yml"
        self.terminate_pb = "/terminate.yml"
        self.opts = Bunch(
            ssh=Bunch(transport="paramiko"),
            spawn_in_advance=False,
            frontend_url="http://example.com/",
            frontend_auth="12345678",
            build_groups={
                "3": {
                    "spawn_playbook": self.spawn_pb,
                    "terminate_playbook": self.terminate_pb,
                    "name": "3"
                }
            },
            terminate_vars=[],

            fedmsg_enabled=False,
            sleeptime=0.1,
            do_sign=True,
            worker_logdir=self.tmp_dir_path,
            timeout=1800,
            destdir=self.tmp_dir_path,
            results_baseurl="/tmp",

            consecutive_failure_threshold=10,
        )
        self.job = BuildJob(self.task, self.opts)

        self.try_spawn_args = '-c ssh {}'.format(self.spawn_pb)

        self.worker_num = 2
        self.group_id = "3"
        self.events = multiprocessing.Queue()
        self.ip = "192.168.1.1"
        self.worker_callback = MagicMock()
        self.worker_fe_callback = MagicMock()
        self.events = multiprocessing.Queue()
        self.logfile_path = os.path.join(self.tmp_dir_path, "test.log")

    @pytest.fixture
    def init_worker(self):
        self.worker = Worker(
            opts=self.opts,
            events=self.events,
            worker_num=self.worker_num,
            group_id=self.group_id,
            callback=self.worker_callback,
        )

        def set_ip(*args, **kwargs):
            self.worker.vm_ip = self.vm_ip

        def erase_ip(*args, **kwargs):
            self.worker.vm_ip = None

        self.set_ip = set_ip

    @pytest.fixture
    def reg_vm(self):
        # call only with init_worker fixture
        self.worker.vm_name = self.vm_name
        self.worker.vm_ip = self.vm_ip

    def teardown_method(self, method):
        # print("\nremove: {}".format(self.tmp_dir_path))
        shutil.rmtree(self.tmp_dir_path)

    def test_init_worker_wo_callback(self):
        worker = Worker(
            opts=self.opts,
            events=self.events,
            worker_num=self.worker_num,
            group_id=self.group_id,
        )
        assert worker.callback

    def test_pkg_built_before(self):
        assert not Worker.pkg_built_before(self.pkg_path, self.CHROOT, self.tmp_dir_path)
        target_dir = os.path.join(self.tmp_dir_path, self.CHROOT, self.pkg_pdn)
        os.makedirs(target_dir)
        assert not Worker.pkg_built_before(self.pkg_path, self.CHROOT, self.tmp_dir_path)
        with open(os.path.join(target_dir, "fail"), "w") as handle:
            handle.write("undone")
        assert not Worker.pkg_built_before(self.pkg_path, self.CHROOT, self.tmp_dir_path)
        os.remove(os.path.join(target_dir, "fail"))
        with open(os.path.join(target_dir, "success"), "w") as handle:
            handle.write("done")
        assert Worker.pkg_built_before(self.pkg_path, self.CHROOT, self.tmp_dir_path)

    def test_spawn_instance_with_check(self, init_worker):
        self.worker.spawn_instance = MagicMock()

        self.worker.spawn_instance.side_effect = self.set_ip

        self.worker.spawn_instance_with_check()
        assert self.vm_ip == self.worker.vm_ip

    def test_spawn_instance_with_check_no_ip(self, init_worker):
        self.worker.spawn_instance = MagicMock()

        with pytest.raises(CoprWorkerError):
            self.worker.spawn_instance_with_check()

    def test_spawn_instance_with_check_ansible_error_reraised(self, init_worker):
        self.worker.spawn_instance = MagicMock()
        self.worker.spawn_instance.side_effect = AnsibleError("foobar")

        # with pytest.raises():
        with pytest.raises(AnsibleError):
            self.worker.spawn_instance_with_check()

    def test_spawn_instance_missing_playbook_for_group_id(self, init_worker):
        self.worker.try_spawn = MagicMock()
        self.worker.validate_vm = MagicMock()
        self.worker.group_id = "175"

        self.worker.spawn_instance()
        assert self.worker.vm_ip is None
        assert not self.worker.try_spawn.called
        assert not self.worker.validate_vm.called

    def test_spawn_instance_ok_immediately(self, init_worker):
        self.worker.try_spawn = MagicMock()
        self.worker.try_spawn.return_value = self.vm_ip
        self.worker.validate_vm = MagicMock()

        self.worker.spawn_instance()
        assert self.worker.vm_ip == self.vm_ip
        assert self.worker.try_spawn.called
        assert self.worker.validate_vm.called

    def test_spawn_instance_error_once_try_spawn(self, init_worker):
        self.worker.try_spawn = MagicMock()
        self.worker.try_spawn.side_effect = [
            CoprWorkerSpawnFailError("foobar"),
            self.vm_ip
        ]
        self.worker.validate_vm = MagicMock()

        self.worker.spawn_instance()
        assert self.worker.vm_ip == self.vm_ip

        assert len(self.worker.try_spawn.call_args_list) == 2
        assert len(self.worker.validate_vm.call_args_list) == 1

    def test_spawn_instance_error_once_validate_new_vm(self, init_worker):
        self.worker.run_ansible_playbook = MagicMock()

        self.worker.try_spawn = MagicMock()
        self.worker.try_spawn.return_value = self.vm_ip
        self.worker.validate_vm = MagicMock()
        self.worker.validate_vm.side_effect = [
            CoprWorkerSpawnFailError("foobar"),
            None,
        ]

        self.worker.spawn_instance()
        assert self.worker.vm_ip == self.vm_ip

        assert len(self.worker.try_spawn.call_args_list) == 2
        assert len(self.worker.validate_vm.call_args_list) == 2

    def test_spawn_instance_ok_immediately_passed_args(self, init_worker):
        self.worker.try_spawn = MagicMock()
        self.worker.try_spawn.return_value = self.vm_ip
        self.worker.validate_vm = MagicMock()

        self.worker.spawn_instance()

        assert self.worker.try_spawn.called
        assert self.worker.validate_vm.called

        assert self.worker.try_spawn.call_args == mock.call(self.try_spawn_args)

    def test_try_spawn_ansible_error_no_result(self, init_worker):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        mc_run_ans.return_value = None

        with pytest.raises(CoprWorkerSpawnFailError):
            self.worker.try_spawn(self.try_spawn_args)

    def test_try_spawn_ansible_ok_no_vm_name(self, init_worker):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        mc_run_ans.return_value = "foobar IP={}".format(self.vm_ip)

        assert self.worker.try_spawn(self.try_spawn_args) == self.vm_ip

    def test_try_spawn_ansible_ok_with_vm_name(self, init_worker):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        mc_run_ans.return_value = "foobar \"IP={}\" adsf \"vm_name={}\"".format(
            self.vm_ip, self.vm_name)

        assert self.worker.try_spawn(self.try_spawn_args) == self.vm_ip
        assert self.worker.vm_name == self.vm_name

    def test_try_spawn_ansible_bad_ip_no_vm_name(self, init_worker):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        for bad_ip in ["256.0.0.2", "not-an-ip", "example.com", ""]:
            mc_run_ans.return_value = "foobar IP={}".format(bad_ip)

            with pytest.raises(CoprWorkerSpawnFailError):
                self.worker.try_spawn(self.try_spawn_args)

    @mock.patch("backend.daemons.dispatcher.ansible.runner.Runner")
    def test_validate_new_vm(self, mc_runner, init_worker, reg_vm):
        mc_ans_conn = MagicMock()
        mc_ans_conn.run.return_value = {"contacted": {self.vm_ip: "ok"}}
        mc_runner.return_value = mc_ans_conn

        self.worker.validate_vm()
        assert mc_ans_conn.run.called

    @mock.patch("backend.daemons.dispatcher.ansible.runner.Runner")
    def test_validate_new_vm_ans_error(self, mc_runner, init_worker, reg_vm):
        mc_ans_conn = MagicMock()
        mc_ans_conn.run.side_effect = IOError()
        mc_runner.return_value = mc_ans_conn

        with pytest.raises(CoprWorkerSpawnFailError):
            self.worker.validate_vm()
        assert mc_ans_conn.run.called

    @mock.patch("backend.daemons.dispatcher.ansible.runner.Runner")
    def test_validate_new_vm_bad_response(self, mc_runner, init_worker, reg_vm):
        mc_ans_conn = MagicMock()
        mc_ans_conn.run.return_value = {"contacted": {}}
        mc_runner.return_value = mc_ans_conn

        with pytest.raises(CoprWorkerSpawnFailError):
            self.worker.validate_vm()
        assert mc_ans_conn.run.called

    def test_terminate_instance(self, init_worker, reg_vm):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans

        self.worker.terminate_instance()
        assert mc_run_ans.called
        expected_call = mock.call(
            "-c ssh {} ".format(self.terminate_pb),
            'terminate instance')
        assert expected_call == mc_run_ans.call_args
        assert self.worker.vm_ip is None
        assert self.worker.vm_name is None

    def test_terminate_instance_with_vm_name(self, init_worker, reg_vm):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        self.opts.terminate_vars = ["vm_name"]

        self.worker.terminate_instance()
        assert mc_run_ans.called
        expected_call = mock.call(
            '-c ssh {} --extra-vars=\'{{"copr_task": {{"vm_name": "{}"}}}}\''
            .format(self.terminate_pb, self.vm_name),
            'terminate instance')

        assert expected_call == mc_run_ans.call_args
        assert self.worker.vm_ip is None
        assert self.worker.vm_name is None

    def test_terminate_instance_with_ip_and_vm_name(self, init_worker, reg_vm):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        self.opts.terminate_vars = ["ip", "vm_name"]

        self.worker.terminate_instance()
        assert mc_run_ans.called

        expected_call = mock.call(
            '-c ssh {} --extra-vars=\''
            '{{"copr_task": {{"vm_name": "{}", "ip": "{}"}}}}\''
            .format(self.terminate_pb, self.vm_name, self.vm_ip),
            'terminate instance')

        assert expected_call == mc_run_ans.call_args
        assert self.worker.vm_ip is None
        assert self.worker.vm_name is None

    def test_terminate_instance_missed_playbook(self, init_worker, reg_vm):
        mc_run_ans = MagicMock()
        self.worker.run_ansible_playbook = mc_run_ans
        self.worker.group_id = "322"

        with pytest.raises(SystemExit):
            self.worker.terminate_instance()
        assert not mc_run_ans.called

    @mock.patch("backend.daemons.dispatcher.fedmsg")
    def test_event(self, mc_fedmsg, init_worker):
        template = "foo: {foo}, bar: {bar}"
        content = {"foo": "foo", "bar": "bar"}
        topic = "copr_test"

        self.worker.opts.fedmsg_enabled = True
        self.worker.event(topic, template, content)
        el = self.worker.events.get()

        assert el["who"] == "worker-2"
        assert el["what"] == "foo: foo, bar: bar"

    @mock.patch("backend.daemons.dispatcher.fedmsg")
    def test_event_error(self, mc_fedmsg, init_worker):
        template = "foo: {foo}, bar: {bar}"
        content = {"foo": "foo", "bar": "bar"}
        topic = "copr_test"
        mc_fedmsg.publish.side_effect = IOError()

        self.worker.opts.fedmsg_enabled = True
        self.worker.event(topic, template, content)
        el = self.worker.events.get()

        assert el["who"] == "worker-2"
        assert el["what"] == "foo: foo, bar: bar"

    @mock.patch("backend.daemons.dispatcher.fedmsg")
    def test_event_disable_fedmsg(self, mc_fedmsg, init_worker):
        template = "foo: {foo}, bar: {bar}"
        content = {"foo": "foo", "bar": "bar"}
        topic = "copr_test"
        mc_fedmsg.publish.side_effect = IOError()

        self.worker.event(topic, template, content)
        assert not mc_fedmsg.publish.called

    @mock.patch("backend.daemons.dispatcher.subprocess")
    def test_run_ansible_playbook_first_try_ok(self, mc_subprocess, init_worker):
        exptected_result = "ok"
        mc_subprocess.check_output.return_value = exptected_result

        assert self.worker.run_ansible_playbook(self.try_spawn_args) == exptected_result

        assert mc_subprocess.check_output.called_once
        assert mc_subprocess.check_output.call_args == mock.call(
            'ansible-playbook -c ssh /spawn.yml', shell=True)

    @mock.patch("backend.daemons.dispatcher.time")
    @mock.patch("backend.daemons.dispatcher.subprocess")
    def test_run_ansible_playbook_first_second_ok(self, mc_subprocess,
                                                  mc_time, init_worker, capsys):
        expected_result = "ok"
        mc_subprocess.check_output.side_effect = [
            CalledProcessError(1, ""),
            expected_result,
        ]

        self.worker.run_ansible_playbook(self.try_spawn_args)
        stdout, stderr = capsys.readouterr()
        assert len(mc_subprocess.check_output.call_args_list) == 2

    @mock.patch("backend.daemons.dispatcher.time")
    @mock.patch("backend.daemons.dispatcher.subprocess")
    def test_run_ansible_playbook_all_attempts_failed(self, mc_subprocess,
                                                      mc_time, init_worker, capsys):
        expected_result = "ok"
        mc_subprocess.check_output.side_effect = [
            CalledProcessError(1, ""),
            CalledProcessError(1, ""),
            expected_result,
        ]

        assert self.worker.run_ansible_playbook(self.try_spawn_args, attempts=2) is None
        assert len(mc_subprocess.check_output.call_args_list) == 2
        stdout, stderr = capsys.readouterr()

    def test_worker_callback(self):
        wc = WorkerCallback(self.logfile_path)

        assert not os.path.exists(self.logfile_path)
        msg = "foobar"
        wc.log(msg)

        with open(self.logfile_path) as handle:
            obtained = handle.read()
            assert msg in obtained

    @mock.patch("backend.daemons.dispatcher.open", create=True)
    def test_worker_callback_error(self, mc_open, capsys):
        wc = WorkerCallback(self.logfile_path)
        mc_open.side_effect = IOError()

        wc.log("foobar")
        stdout, stderr = capsys.readouterr()

        assert "Could not write to logfile" in stderr

        assert not os.path.exists(self.logfile_path)

    def test_mark_started(self, init_worker):
        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.mark_started(self.job)

        expected_call = mock.call({'builds': [
            {'status': 3, 'build_id': self.job_build_id,
             'project_name': 'copr_name', 'submitter': None,
             'project_owner': 'copr_owner', 'repos': [],
             'results': u'/tmp/copr_owner/copr_name/',
             'destdir': self.DESTDIR,
             'started_on': None, 'submitted_on': None, 'chroot': 'fedora-20-x86_64',
             'ended_on': None, 'built_packages': '', 'timeout': 1800, 'pkg_version': '',
             'pkg_epoch': None, 'pkg_main_version': '', 'pkg_release': None,
             'memory_reqs': None, 'buildroot_pkgs': None, 'id': self.job_build_id,
             'pkg': self.SRC_PKG_URL, "enable_net": True}
        ]})

        assert expected_call == self.worker_fe_callback.update.call_args

    def test_mark_started_error(self, init_worker):
        self.worker.frontend_callback = self.worker_fe_callback
        self.worker_fe_callback.update.side_effect = IOError()

        with pytest.raises(CoprWorkerError):
            self.worker.mark_started(self.job)

    def test_return_results(self, init_worker):
        self.job.started_on = self.test_time
        self.job.ended_on = self.test_time + 10

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.mark_started(self.job)

        expected_call = mock.call({'builds': [
            {'status': 3, 'build_id': self.job_build_id,
             'project_name': 'copr_name', 'submitter': None,
             'project_owner': 'copr_owner', 'repos': [],
             'results': u'/tmp/copr_owner/copr_name/',
             'destdir': self.DESTDIR,
             'started_on': self.job.started_on, 'submitted_on': None, 'chroot': 'fedora-20-x86_64',
             'ended_on': self.job.ended_on, 'built_packages': '', 'timeout': 1800, 'pkg_version': '',
             'pkg_epoch': None, 'pkg_main_version': '', 'pkg_release': None,
             'memory_reqs': None, 'buildroot_pkgs': None, 'id': self.job_build_id,
             'pkg': self.SRC_PKG_URL, "enable_net": True}
        ]})

        assert expected_call == self.worker_fe_callback.update.call_args

    def test_return_results_error(self, init_worker):
        self.job.started_on = self.test_time
        self.job.ended_on = self.test_time + 10

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker_fe_callback.update.side_effect = IOError()

        with pytest.raises(CoprWorkerError):
            self.worker.return_results(self.job)

    def test_starting_builds(self, init_worker):
        self.job.started_on = self.test_time
        self.job.ended_on = self.test_time + 10

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.starting_build(self.job)

        expected_call = mock.call(self.job_build_id, self.CHROOT)
        assert expected_call == self.worker_fe_callback.starting_build.call_args

    def test_starting_build_error(self, init_worker):
        self.worker.frontend_callback = self.worker_fe_callback
        self.worker_fe_callback.starting_build.side_effect = IOError()

        with pytest.raises(CoprWorkerError):
            self.worker.starting_build(self.job)

    @mock.patch("backend.daemons.dispatcher.MockRemote")
    @mock.patch("backend.daemons.dispatcher.os")
    def test_do_job_failure_on_mkdirs(self, mc_os, mc_mr, init_worker, reg_vm):
        mc_os.path.exists.return_value = False
        mc_os.makedirs.side_effect = IOError()

        self.worker.frontend_callback = self.worker_fe_callback

        self.worker.do_job(self.job)
        assert self.job.status == BuildStatus.FAILURE
        assert not mc_mr.called

    @mock.patch("backend.daemons.dispatcher.MockRemote")
    def test_do_job(self, mc_mr_class, init_worker, reg_vm):
        assert not os.path.exists(self.DESTDIR_CHROOT)

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.do_job(self.job)
        assert self.job.status == BuildStatus.SUCCEEDED
        assert os.path.exists(self.DESTDIR_CHROOT)

    @mock.patch("backend.daemons.dispatcher.MockRemote")
    def test_do_job_updates_details(self, mc_mr_class, init_worker, reg_vm):
        assert not os.path.exists(self.DESTDIR_CHROOT)
        mc_mr_class.return_value.build_pkg.return_value = {
            "results": self.test_time,
        }

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.do_job(self.job)
        assert self.job.status == BuildStatus.SUCCEEDED
        assert self.job.results == self.test_time
        assert os.path.exists(self.DESTDIR_CHROOT)

    @mock.patch("backend.daemons.dispatcher.MockRemote")
    def test_do_job_mr_error(self, mc_mr_class, init_worker, reg_vm):
        mc_mr_class.return_value.build_pkg.side_effect = MockRemoteError("foobar")

        self.worker.frontend_callback = self.worker_fe_callback
        self.worker.do_job(self.job)
        assert self.job.status == BuildStatus.FAILURE

    @mock.patch("backend.daemons.dispatcher.fedmsg")
    def test_init_fedmsg(self, mc_fedmsg, init_worker):
        self.worker.init_fedmsg()
        assert not mc_fedmsg.init.called
        self.worker.opts.fedmsg_enabled = True
        self.worker.init_fedmsg()
        assert mc_fedmsg.init.called

        mc_fedmsg.init.side_effect = KeyError()
        self.worker.init_fedmsg()

    def test_obtain_job(self, init_worker):
        mc_tq = MagicMock()
        self.worker.task_queue = mc_tq
        self.worker.starting_build = MagicMock()
        self.worker.pkg_built_before = MagicMock()
        self.worker.pkg_built_before.return_value = False

        mc_tq.dequeue.return_value = MagicMock(data=self.task)
        obtained_job = self.worker.obtain_job()
        assert obtained_job.__dict__ == self.job.__dict__
        assert self.worker.pkg_built_before.called

    def test_obtain_job_skip_pkg(self, init_worker):
        mc_tq = MagicMock()
        self.worker.task_queue = mc_tq
        self.worker.starting_build = MagicMock()
        self.worker.pkg_built_before = MagicMock()
        self.worker.pkg_built_before.return_value = True
        self.worker.mark_started = MagicMock()
        self.worker.return_results = MagicMock()

        mc_tq.dequeue.return_value = MagicMock(data=self.task)
        assert self.worker.obtain_job() is None
        assert self.worker.pkg_built_before.called

    def test_obtain_job_dequeue_type_error(self, init_worker):
        mc_tq = MagicMock()
        self.worker.task_queue = mc_tq
        self.worker.starting_build = MagicMock()
        self.worker.pkg_built_before = MagicMock()
        self.worker.pkg_built_before.return_value = False

        mc_tq.dequeue.side_effect = TypeError()
        assert self.worker.obtain_job() is None
        assert not self.worker.starting_build.called
        assert not self.worker.pkg_built_before.called

    def test_obtain_job_dequeue_none_result(self, init_worker):
        mc_tq = MagicMock()
        self.worker.task_queue = mc_tq
        self.worker.starting_build = MagicMock()
        self.worker.pkg_built_before = MagicMock()
        self.worker.pkg_built_before.return_value = False

        mc_tq.dequeue.return_value = None
        assert self.worker.obtain_job() is None
        assert not self.worker.starting_build.called
        assert not self.worker.pkg_built_before.called

    def test_obtain_job_on_starting_build(self, init_worker):
        mc_tq = MagicMock()
        self.worker.task_queue = mc_tq
        self.worker.starting_build = MagicMock()
        self.worker.starting_build.return_value = False
        self.worker.pkg_built_before = MagicMock()
        self.worker.pkg_built_before.return_value = False

        mc_tq.dequeue.return_value = MagicMock(data=self.task)
        assert self.worker.obtain_job() is None
        assert not self.worker.pkg_built_before.called

    @mock.patch("backend.daemons.dispatcher.time")
    def test_run(self, mc_time, init_worker):
        self.worker.init_fedmsg = MagicMock()
        self.worker.spawn_instance_with_check = MagicMock()
        self.worker.spawn_instance_with_check.return_value = self.vm_ip

        self.worker.obtain_job = MagicMock()
        self.worker.obtain_job.return_value = self.job

        def validate_not_spawn():
            assert not self.worker.spawn_instance_with_check.called
            return mock.DEFAULT

        self.worker.obtain_job.side_effect = validate_not_spawn
        self.worker.terminate_instance = MagicMock()

        mc_do_job = MagicMock()
        self.worker.do_job = mc_do_job

        def stop_loop(*args, **kwargs):
            self.worker.kill_received = True

        mc_do_job.side_effect = stop_loop

        self.worker.run()
        assert mc_do_job.called
        assert self.worker.init_fedmsg.called
        assert self.worker.obtain_job.called
        assert self.worker.terminate_instance.called

    @mock.patch("backend.daemons.dispatcher.time")
    def test_run_spawn_in_advance(self, mc_time, init_worker):
        self.worker.opts.spawn_in_advance = True
        self.worker.init_fedmsg = MagicMock()
        self.worker.spawn_instance_with_check = MagicMock()
        self.worker.spawn_instance_with_check.side_effect = self.set_ip

        self.worker.obtain_job = MagicMock()
        self.worker.obtain_job.return_value = self.job

        def validate_spawn():
            assert self.worker.spawn_instance_with_check.called
            self.worker.spawn_instance_with_check.reset_mock()
            return mock.DEFAULT

        self.worker.obtain_job.side_effect = validate_spawn
        self.worker.terminate_instance = MagicMock()

        mc_do_job = MagicMock()
        self.worker.do_job = mc_do_job

        def stop_loop(*args, **kwargs):
            assert not self.worker.spawn_instance_with_check.called
            self.worker.kill_received = True

        mc_do_job.side_effect = stop_loop

        self.worker.run()

    @mock.patch("backend.daemons.dispatcher.time")
    def test_run_spawn_in_advance_with_existing_vm(self, mc_time, init_worker):
        self.worker.opts.spawn_in_advance = True
        self.worker.init_fedmsg = MagicMock()
        self.worker.spawn_instance_with_check = MagicMock()
        self.worker.spawn_instance_with_check.side_effect = self.set_ip

        self.worker.check_vm_still_alive = MagicMock()

        self.worker.obtain_job = MagicMock()
        self.worker.obtain_job.side_effect = [
            None,
            self.job,
        ]

        def validate_spawn():
            assert self.worker.spawn_instance_with_check.called
            self.worker.spawn_instance_with_check.reset_mock()
            return mock.DEFAULT

        self.worker.obtain_job.side_effect = validate_spawn
        self.worker.terminate_instance = MagicMock()

        mc_do_job = MagicMock()
        self.worker.do_job = mc_do_job

        def stop_loop(*args, **kwargs):
            assert not self.worker.spawn_instance_with_check.called
            self.worker.kill_received = True

        mc_do_job.side_effect = stop_loop

        self.worker.run()
        assert self.worker.check_vm_still_alive.called
        assert self.worker.spawn_instance_with_check.called_once

    def test_check_vm_still_alive(self, init_worker):
        self.worker.validate_vm = MagicMock()
        self.worker.terminate_instance = MagicMock()

        self.worker.check_vm_still_alive()

        assert not self.worker.validate_vm.called
        assert not self.worker.terminate_instance.called

    def test_check_vm_still_alive_ok(self, init_worker, reg_vm):
        self.worker.validate_vm = MagicMock()
        self.worker.terminate_instance = MagicMock()

        self.worker.check_vm_still_alive()

        assert self.worker.validate_vm.called
        assert not self.worker.terminate_instance.called

    def test_check_vm_still_alive_not_ok(self, init_worker, reg_vm):
        self.worker.validate_vm = MagicMock()
        self.worker.validate_vm.side_effect = CoprWorkerSpawnFailError("foobar")
        self.worker.terminate_instance = MagicMock()

        self.worker.check_vm_still_alive()

        assert self.worker.validate_vm.called
        assert self.worker.terminate_instance.called

    @mock.patch("backend.daemons.dispatcher.time")
    def test_run_finalize(self, mc_time, init_worker):
        self.worker.init_fedmsg = MagicMock()
        self.worker.obtain_job = MagicMock()
        self.worker.obtain_job.return_value = self.job
        self.worker.spawn_instance_with_check = MagicMock()
        self.worker.spawn_instance_with_check.return_value = self.vm_ip
        self.worker.terminate_instance = MagicMock()

        mc_do_job = MagicMock()
        self.worker.do_job = mc_do_job

        def stop_loop(*args, **kwargs):
            self.worker.kill_received = True
            raise IOError()

        mc_do_job.side_effect = stop_loop

        self.worker.run()

        assert mc_do_job.called
        assert self.worker.init_fedmsg.called
        assert self.worker.obtain_job.called
        assert self.worker.terminate_instance.called

    @mock.patch("backend.daemons.dispatcher.time")
    def test_run_no_job(self, mc_time, init_worker):
        self.worker.init_fedmsg = MagicMock()
        self.worker.obtain_job = MagicMock()
        self.worker.obtain_job.return_value = None
        self.worker.spawn_instance_with_check = MagicMock()
        self.worker.spawn_instance_with_check.return_value = self.vm_ip
        self.worker.terminate_instance = MagicMock()

        mc_do_job = MagicMock()
        self.worker.do_job = mc_do_job

        def stop_loop(*args, **kwargs):
            self.worker.kill_received = True

        mc_time.sleep.side_effect = stop_loop

        self.worker.run()

        assert not mc_do_job.called
        assert self.worker.init_fedmsg.called
        assert self.worker.obtain_job.called
        assert not self.worker.terminate_instance.called
