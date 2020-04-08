# coding: utf-8

import copy
import json

import logging
from munch import Munch
import time
import requests

from copr_backend.exceptions import CoprJobGrabError

from retask.queue import Queue

import tempfile
import shutil
import os

from unittest import mock
from unittest.mock import patch, MagicMock, call
import pytest

from copr_backend.daemons.job_grab import CoprJobGrab
import copr_backend.actions


MODULE_REF = "copr_backend.daemons.job_grab"

@pytest.yield_fixture
def mc_logging():
    with mock.patch("{}.logging".format(MODULE_REF)) as mc_logging:
        yield mc_logging


@pytest.yield_fixture
def mc_setproctitle():
    with mock.patch("{}.setproctitle".format(MODULE_REF)) as mc_spt:
        yield mc_spt


@pytest.yield_fixture
def mc_retask_queue():
    with mock.patch("{}.jobgrabcontrol.Channel".format(MODULE_REF)) as mc_queue:
        def make_queue(*args, **kwargs):
            updated_kwargs = copy.deepcopy(kwargs)
            updated_kwargs["spec"] = Queue
            mc = MagicMock(**updated_kwargs)
            return mc

        mc_queue.side_effect = make_queue
        yield mc_queue


@pytest.yield_fixture
def mc_grc():
    with mock.patch("{}.get_redis_connection".format(MODULE_REF)) as handle:
        yield handle


class TestJobGrab(object):

    def setup_method(self, method):

        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

        self.log_dir = os.path.join(self.tmp_dir_path, "copr")
        self.log_file = os.path.join(self.log_dir, "copr.log")

        self.opts = Munch(
            verbose=False,
            build_groups=[
                {"id": 0, "name": "x86",
                 "archs": ["i386", "i686", "x86_64"],
                 "max_vm_per_user": 5},
                {"id": 1, "name": "arm", "archs": ["armv7"],
                 "max_vm_per_user": 5},
            ],
            destdir="/dev/null",
            frontend_base_url="http://example.com",
            frontend_auth="foobar",
            results_baseurl="http://example.com/results/",
            sleeptime=1,

            redis_host="127.0.0.1",
            redis_port=6379,
            redis_db=0,
        )

        self.queue = MagicMock()
        self.lock = MagicMock()
        self.frontend_client = MagicMock()

        self.task_dict_1 = dict(
            task_id=12345,
            chroot="fedora-20-x86_64",
            project_owner="foobar",
        )
        self.task_dict_2 = dict(
            task_id=12346,
            chroot="fedora-20-armv7",
            project_owner="foobar",
        )
        self.task_dict_bad_arch = dict(
            task_id=12346,
            chroot="fedora-20-s390x",
            project_owner="foobar",
        )


    def teardown_method(self, method):

        shutil.rmtree(self.tmp_dir_path)
        if hasattr(self, "cbl"):
            del self.cbl

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    @pytest.yield_fixture
    def mc_time(self):
        with mock.patch("{}.time".format(MODULE_REF)) as mc_time:
            mc_time.time.return_value = self.test_time
            yield mc_time

    @pytest.fixture
    def init_jg(self, mc_retask_queue, mc_grc):
        self.jg = CoprJobGrab(self.opts)
        self.jg.init_internal_structures()
        self.jg.jg_control = MagicMock()

    def test_listen_to_pubsub(self, mc_retask_queue, mc_grc):
        mc_rc = MagicMock()
        mc_grc.return_value = mc_rc
        self.jg = CoprJobGrab(self.opts)

        assert not mc_rc.pubsub.called
        self.jg.listen_to_pubsub()

        assert mc_rc.pubsub.called
        assert mc_rc.pubsub.return_value.subscribe.called

    def test_route_build_task_skip_added(self, init_jg):
        for d in [self.task_dict_1, self.task_dict_2]:
            self.jg.added_jobs_dict[d["task_id"]] = d

        assert self.jg.route_build_task(self.task_dict_1) == 0
        assert not self.jg.jg_control.add_build.called

    def test_route_build_task_skip_too_much_added(self, init_jg):
        for i in range(10):
            task = dict(self.task_dict_1)
            task["task_id"] = 1000 + i
            self.jg.added_jobs_dict[task["task_id"]] = task

        assert self.jg.route_build_task(self.task_dict_1) == 0
        assert not self.jg.jg_control.add_build.called

    def test_route_build_task_missing_task_ud(self, init_jg):
        assert self.jg.route_build_task({"task": "wrong_key"}) == 0
        assert not self.jg.jg_control.add_build.called

    def test_route_build_task_correct_group_1(self, init_jg,):
        assert self.jg.route_build_task(self.task_dict_1) == 1
        assert self.jg.jg_control.add_build.call_args[0][0] == 0

    def test_route_build_task_correct_group_2(self, init_jg, ):
        assert self.jg.route_build_task(self.task_dict_2) == 1
        assert self.jg.jg_control.add_build.call_args[0][0] == 1

    def test_route_build_task_correct_group_error(self, init_jg):
        with pytest.raises(CoprJobGrabError) as err:
            self.jg.route_build_task(self.task_dict_bad_arch)

    @mock.patch("copr_backend.daemons.job_grab.Action", spec=copr_backend.actions.Action)
    def test_process_action(self, mc_action, init_jg):
        test_action = MagicMock()

        self.jg.process_action(test_action)

        expected_call = call(self.opts, test_action, frontend_client=self.jg.frontend_client)
        assert expected_call == mc_action.call_args
        assert mc_action.return_value.run.called

    @mock.patch("copr_backend.daemons.job_grab.get")
    def test_load_tasks_error_request(self, mc_get, init_jg):
        mc_get.side_effect = requests.RequestException()

        self.jg.route_build_task = MagicMock()
        self.jg.event = MagicMock()
        self.jg.process_action = MagicMock()

        assert self.jg.load_tasks() is None

        assert not self.jg.route_build_task.called
        assert not self.jg.process_action.called

    @mock.patch("copr_backend.daemons.job_grab.get")
    def test_load_tasks_error_request_json(self, mc_get, init_jg):
        mc_get.return_value.json.side_effect = ValueError()

        self.jg.route_build_task = MagicMock()
        self.jg.event = MagicMock()
        self.jg.process_action = MagicMock()

        assert self.jg.load_tasks() is None

        assert not self.jg.route_build_task.called
        assert not self.jg.process_action.called

    @mock.patch("copr_backend.daemons.job_grab.get")
    def test_load_tasks_builds(self, mc_get, init_jg):
        mc_get.return_value.json.return_value = {
            "builds": [
                self.task_dict_1,
                self.task_dict_2,
                self.task_dict_2
            ]
        }

        self.jg.route_build_task = MagicMock()
        self.jg.route_build_task.side_effect = [
            1,
            1,
            CoprJobGrabError("foobar"),
        ]
        self.jg.event = MagicMock()
        self.jg.process_action = MagicMock()

        self.jg.load_tasks()

        assert len(self.jg.route_build_task.call_args_list) == 3
        assert not self.jg.process_action.called

    @mock.patch("copr_backend.daemons.job_grab.get")
    def test_load_tasks_actions(self, mc_get, init_jg):
        action_1 = MagicMock()
        action_2 = MagicMock()
        mc_get.return_value.json.return_value = {
            "actions": [
                action_1,
                action_2,
            ],
            "builds": [],
        }

        self.jg.route_build_task = MagicMock()
        self.jg.event = MagicMock()
        self.jg.process_action = MagicMock()

        self.jg.load_tasks()

        expected_calls = [call(action_1), call(action_2)]
        assert self.jg.process_action.call_args_list == expected_calls

    @mock.patch("copr_backend.daemons.job_grab.get")
    def test_regression_load_tasks_actions_(self, mc_get, init_jg):
        """
        https://bugzilla.redhat.com/show_bug.cgi?id=1182106
        """
        action_1 = MagicMock()
        action_2 = MagicMock()
        mc_get.return_value.json.return_value = {
            "actions": [
                action_1,
                action_2,
            ],
            "builds": [],
        }

        self.jg.route_build_task = MagicMock()
        self.jg.event = MagicMock()
        self.jg.process_action = MagicMock()

        # load_tasks should suppress this error
        self.jg.process_action.side_effect = IOError()

        self.jg.load_tasks()

        expected_calls = [call(action_1), call(action_2)]
        assert self.jg.process_action.call_args_list == expected_calls

    # todo: replace with test for method on_pubsub_event
    # def test_process_task_end_pubsub(self, init_jg, mc_grc):
    #     self.jg.added_jobs = MagicMock()
    #     self.jg.frontend_client = MagicMock()
    #     mc_rc = MagicMock()
    #     mc_grc.return_value = mc_rc
    #     mc_ch = MagicMock()
    #     mc_rc.pubsub.return_value = mc_ch
    #     self.jg.channel = mc_ch
    #     self.stage = 0
    #
    #     def on_get_message():
    #         self.stage += 1
    #
    #         if self.stage == 1:
    #             return {}
    #         elif self.stage == 2:
    #             assert not self.jg.added_jobs.remove.called
    #             return {"type": "subscribe"}  # wrong type
    #         elif self.stage == 3:
    #             assert not self.jg.added_jobs.remove.called
    #             return {"type": "message", "data": "{{{"}  # mall-formed json
    #         elif self.stage == 4:
    #             assert not self.jg.added_jobs.remove.called
    #             return {"type": "message", "data": json.dumps({})}  # missing action
    #         elif self.stage == 5:
    #             assert not self.jg.added_jobs.remove.called
    #             return {"type": "message", "data": json.dumps({"action": "foobar"})}  # unsupported action
    #         elif self.stage == 6:
    #             assert not self.jg.added_jobs.remove.called
    #             msg = {"action": "remove"}
    #             return {"type": "message", "data": json.dumps(msg)}  # missing "task_id"
    #         elif self.stage == 7:
    #             assert not self.jg.added_jobs.remove.called
    #             msg = {"action": "remove", "task_id": "123-fedora"}
    #             self.jg.added_jobs.__contains__.return_value = False
    #             return {"type": "message", "data": json.dumps(msg)}  # task "id" not in self.added_jobs
    #         elif self.stage == 8:
    #             assert not self.jg.added_jobs.remove.called
    #             # import ipdb; ipdb.set_trace()
    #             self.jg.added_jobs.__contains__.return_value = True
    #             msg = {"action": "remove", "task_id": "123-fedora"}         # should be removed from added job,
    #             return {"type": "message", "data": json.dumps(msg)}  # reschedule build not called
    #         elif self.stage == 9:
    #             assert self.jg.added_jobs.remove.call_args == mock.call("123-fedora")
    #             msg = {"action": "reschedule", "task_id": "123-fedora"}
    #             return {"type": "message", "data": json.dumps(msg)}  # reschedule build not called
    #         elif self.stage == 10:
    #             assert self.jg.added_jobs.remove.call_args == mock.call("123-fedora")
    #             msg = {"action": "reschedule", "task_id": "123-fedora", "build_id": 123, "chroot": "fedora"}
    #             return {"type": "message", "data": json.dumps(msg)}  # reschedule called
    #         else:
    #             assert self.jg.added_jobs.remove.call_args == mock.call("123-fedora")
    #             assert self.jg.frontend_client.reschedule_build.called
    #
    #         return None
    #
    #     mc_ch.get_message.side_effect = on_get_message
    #     self.jg.process_task_end_pubsub()

    def test_run(self, mc_time, mc_setproctitle, init_jg, mc_grc):
        self.jg.process_task_end_pubsub = MagicMock()
        self.jg.load_tasks = MagicMock()
        self.jg.load_tasks.side_effect = [
            None,
            IOError(),
            KeyError(),
            KeyboardInterrupt
        ]

        self.jg.run()

        assert mc_setproctitle.called
        assert self.jg.load_tasks.called
