import os
import argparse
from collections import defaultdict
import json
from pprint import pprint
from _pytest.capture import capsys
import pytest
import tempfile
import shutil

import six
import time

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

log = logging.getLogger()
log.info("Logger initiated")

from backend.actions import Action, ActionType, ActionResult

import multiprocessing
if six.PY3:
    import queue
    from queue import Empty as EmptyQueue
else:
    import Queue as queue
    from Queue import Empty  as EmptyQueue

@mock.patch("backend.actions.time")
class TestAction(object):

    def setup_method(self, method):
        self.test_q = queue.Queue()
        self.tmp_dir_name = None

        self.test_time = time.time()

        self.pkgs = ["foo.src.rpm", "bar.src.rpm"]
        self.pkgs_stripped = ["foo", "bar"]

        self.ext_data_for_delete_build = json.dumps({
            "pkgs": " ".join(self.pkgs),
            "username": "foo",
            "projectname": "bar"
        })

    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_action_{}".format(time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)
        #print(self.tmp_dir_name)
        os.mkdir(self.tmp_dir_name)
        os.mkdir(os.path.join(self.tmp_dir_name, "old_dir"))

        self.test_content = "time: {}\n".format(self.test_time)



        return self.tmp_dir_name

    def test_action_event(self, mc_time):
        test_action = Action(events=self.test_q, action={}, lock=None,
                             frontend_callback=None, destdir=None, front_url=None)
        with pytest.raises(EmptyQueue):
            test_action.events.get_nowait()

        test_string = "Foo Bar"

        mc_time.time.return_value = self.test_time
        test_action.event(test_string)
        result_dict = test_action.events.get()
        assert result_dict["when"] == self.test_time
        assert result_dict["who"] == "action"
        assert result_dict["what"] == test_string

    def test_action_run_legal_flag(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()
        test_action = Action(
            action={
                "action_type": ActionType.LEGAL_FLAG,
                "id": 1
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=None,
            front_url=None
        )
        test_action.run()
        assert not mc_front_cb.called

        result_dict = self.test_q.get()
        assert result_dict["when"] == self.test_time
        assert result_dict["who"] == "action"
        assert result_dict["what"] == "Action legal-flag: ignoring"
        with pytest.raises(EmptyQueue):
            test_action.events.get_nowait()

    def test_action_run_rename(self, mc_time):

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        with open(os.path.join(self.tmp_dir_name, "old_dir", "foobar.txt"), "w") as handle:
            handle.write(self.test_content)

        test_action = Action(
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert not os.path.exists(os.path.join(tmp_dir, "old_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir", "foobar.txt"))
        with open(os.path.join(tmp_dir, "new_dir", "foobar.txt")) as handle:
            assert handle.read() == self.test_content

    def test_action_run_rename_success_on_empty_src(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        test_action = Action(
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=os.path.join(tmp_dir, "dir-not-exists"),
            front_url=None
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))

    def test_action_run_rename_failure_on_destination_exists(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()
        with open(os.path.join(self.tmp_dir_name, "old_dir", "foobar.txt"), "w") as handle:
            handle.write(self.test_content)
        os.mkdir(os.path.join(tmp_dir, "new_dir"))

        test_action = Action(
            action={
                "action_type": ActionType.RENAME,
                "id": 1,
                "old_value": "old_dir",
                "new_value": "new_dir"
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None
        )
        test_action.run()
        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 1
        assert result_dict["result"] == ActionResult.FAILURE
        assert result_dict["message"] == "Destination directory already exist."
        assert result_dict["job_ended_on"] == self.test_time

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))
        assert os.path.exists(os.path.join(tmp_dir, "new_dir"))
        assert not os.path.exists(os.path.join(tmp_dir, "new_dir", "foobar.txt"))

    def test_action_run_delete_copr(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                "old_value": "old_dir",
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=os.path.join(tmp_dir, "dir-not-exists"),
            front_url=None
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 6
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        event_dict = self.test_q.get_nowait()

        assert event_dict["what"] == "Action delete copr"
        assert event_dict["who"] == "action"
        assert event_dict["when"] == self.test_time
        with pytest.raises(EmptyQueue):
            self.test_q.get_nowait()

        assert os.path.exists(os.path.join(tmp_dir, "old_dir"))

    def test_action_run_delete_copr_remove_folders(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "copr",
                "id": 6,
                "old_value": "old_dir",
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]
        assert result_dict["id"] == 6
        assert result_dict["result"] == ActionResult.SUCCESS
        assert result_dict["job_ended_on"] == self.test_time

        event_dict = self.test_q.get_nowait()

        assert event_dict["what"] == "Action delete copr"
        assert event_dict["who"] == "action"
        assert event_dict["when"] == self.test_time

        event_dict_2 = self.test_q.get_nowait()

        assert "Removing copr" in event_dict_2["what"]
        assert event_dict["who"] == "action"
        assert event_dict["when"] == self.test_time

        assert not os.path.exists(os.path.join(tmp_dir, "old_dir"))

    def test_delete_no_chroot_dirs(self, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        tmp_dir = self.make_temp_dir()

        for obj_type in ["build-succeeded", "build-skipped", "build-failed"]:
            test_action = Action(
                action={
                    "action_type": ActionType.DELETE,
                    "object_type": obj_type,
                    "id": 7,
                    "old_value": "not-existing-project",
                    "data": self.ext_data_for_delete_build,
                },
                events=self.test_q, lock=None,
                frontend_callback=mc_front_cb,
                destdir=tmp_dir,
                front_url=None
            )
            with mock.patch("backend.actions.shutil") as mc_shutil:
                test_action.run()
                assert not mc_shutil.rmtree.called

            ev_1 = self.test_q.get_nowait()
            assert "Action delete build" == ev_1["what"]
            assert ev_1["who"] == "action"

            ev_2 = self.test_q.get_nowait()
            assert "Packages to delete" in ev_2["what"]
            assert " ".join(self.pkgs_stripped) in  ev_2["what"]
            assert ev_2["who"] == "action"

            ev_3 = self.test_q.get_nowait()
            assert "Copr path" in ev_3["what"]
            assert ev_3["who"] == "action"

            with pytest.raises(EmptyQueue):
               self.test_q.get_nowait()

    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (0, "", "")
        #mc_createrepo.side_effect = IOError()

        tmp_dir = self.make_temp_dir()

        chroot_1_dir = os.path.join(tmp_dir, "old_dir", "fedora20")
        os.mkdir(chroot_1_dir)
        foo_pkg_dir = os.path.join(chroot_1_dir, "foo")
        os.mkdir(foo_pkg_dir)
        chroot_2_dir = os.path.join(tmp_dir, "old_dir", "epel7")
        os.mkdir(chroot_2_dir)

        with open(os.path.join(chroot_1_dir, "foo", "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        log_path = os.path.join(chroot_1_dir, "build-42.log")
        with open(log_path, "w") as fh:
             fh.write(self.test_content)

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build-succeeded",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
        )

        assert os.path.exists(foo_pkg_dir)
        test_action.run()
        assert not os.path.exists(foo_pkg_dir)
        assert not os.path.exists(log_path)

        assert_what_from_queue(self.test_q, msg_list=[
            "Action delete build",
            "Packages to delete " + " ".join(self.pkgs_stripped),
            "Copr path",
        ])

        def assert_epel7():
            assert_what_from_queue(self.test_q, msg_list=[
                "Package foo dir not found in chroot epel7",
                "Package bar dir not found in chroot epel7",
            ])


        def assert_fedora20():
            assert_what_from_queue(self.test_q, msg_list=[
                "Removing build ",
                "Running createrepo",
                "Package bar dir not found in chroot fedora20",
                "Running createrepo",

            ])

        ev = self.test_q.get_nowait()
        assert ev["who"] == "action"
        assert "In chroot epel7" in ev["what"] or "In chroot fedora20" in ev["what"]

        if "In chroot epel7" in ev["what"]:
            assert_epel7()
            assert_what_from_queue(self.test_q, msg_list=["In chroot fedora20"])
            assert_fedora20()
        else:
            assert_fedora20()
            assert_what_from_queue(self.test_q, msg_list=["In chroot epel7"])
            assert_epel7()

        assert_what_from_queue(self.test_q, msg_list=["Removing log"])

        with pytest.raises(EmptyQueue):
            self.test_q.get_nowait()

    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded_createrepo_error(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (1, "", "Create repo failed")
        #mc_createrepo.side_effect = IOError()

        tmp_dir = self.make_temp_dir()

        chroot_1_dir = os.path.join(tmp_dir, "old_dir", "fedora20")
        os.mkdir(chroot_1_dir)
        foo_pkg_dir = os.path.join(chroot_1_dir, "foo")
        os.mkdir(foo_pkg_dir)
        chroot_2_dir = os.path.join(tmp_dir, "old_dir", "epel7")
        os.mkdir(chroot_2_dir)

        with open(os.path.join(chroot_1_dir, "foo", "foo.src.rpm"), "w") as fh:
            fh.write("foo\n")

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build-succeeded",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None
        )

        test_action.run()
        error_event_recorded = False

        while not self.test_q.empty():
            ev = self.test_q.get_nowait()
            if "Error making local repo" in ev["what"]:
                error_event_recorded = True

        assert error_event_recorded



def assert_what_from_queue(q, msg_list, who="action"):
    for msg in msg_list:
        ev = q.get_nowait()
        assert ev["who"] == who
        assert msg in ev["what"]
