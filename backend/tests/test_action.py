import os
import json
import tempfile
import shutil
import time
import tarfile

import pytest
import six


if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

# logging.basicConfig(
#     level=logging.INFO,
#     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )
#
# log = logging.getLogger()
# log.info("Logger initiated")

from backend.actions import Action, ActionType, ActionResult

if six.PY3:
    import queue
    from queue import Empty as EmptyQueue
else:
    import Queue as queue
    from Queue import Empty as EmptyQueue


RESULTS_ROOT_URL = "http://example.com/results"
STDOUT = "stdout"
STDERR = "stderr"


def assert_what_from_queue(q, msg_list, who="action"):
    for msg in msg_list:
        ev = q.get_nowait()
        assert ev["who"] == who
        assert msg in ev["what"]

@mock.patch("backend.actions.time")
class TestAction(object):

    def setup_method(self, method):
        self.test_q = queue.Queue()
        self.tmp_dir_name = None

        self.test_time = time.time()

        self.pkgs = ["foo.src.rpm"]
        self.pkgs_stripped = ["foo"]

        self.ext_data_for_delete_build = json.dumps({
            "pkgs": " ".join(self.pkgs),
            "username": "foo",
            "projectname": "bar",
            "chroots": ["fedora20", "epel7"]
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

        os.mkdir(self.tmp_dir_name)
        os.mkdir(os.path.join(self.tmp_dir_name, "old_dir"))

        self.test_content = "time: {}\n".format(self.test_time)

        return self.tmp_dir_name

    def unpack_resource(self, resource_name):
        if self.tmp_dir_name is None:
            self.make_temp_dir()

        src_path = os.path.join(os.path.dirname(__file__),
                                "_resources", resource_name)

        with tarfile.open(src_path, "r:gz") as tfile:
            tfile.extractall(os.path.join(self.tmp_dir_name, "old_dir"))

    def test_action_event(self, mc_time):
        test_action = Action(
            events=self.test_q,
            action={}, lock=None,
            frontend_callback=None,
            destdir=None,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )

        with pytest.raises(EmptyQueue):
            test_action.events.get_nowait()

        test_string = "Foo Bar"

        mc_time.time.return_value = self.test_time
        test_action.add_event(test_string)
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
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

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "id": 7,
                "old_value": "not-existing-project",
                "data": self.ext_data_for_delete_build,
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        with mock.patch("backend.actions.shutil") as mc_shutil:
            test_action.run()
            assert not mc_shutil.rmtree.called

    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (0, "", "")
        # mc_createrepo.side_effect = IOError()

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
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )

        assert os.path.exists(foo_pkg_dir)
        test_action.run()
        assert not os.path.exists(foo_pkg_dir)
        assert not os.path.exists(log_path)

        assert_what_from_queue(self.test_q, msg_list=[
            "Action delete build",
            "Deleting package " + " ".join(self.pkgs_stripped),
            "Copr path",
        ])

        def assert_epel7():
            assert_what_from_queue(self.test_q, msg_list=[
                "Package foo dir not found in chroot epel7",
            ])

        def assert_fedora20():
            assert_what_from_queue(self.test_q, msg_list=[
                "Removing build ",
                "Running createrepo",
            ])

        ev = self.test_q.get_nowait()
        assert ev["who"] == "action"
        assert "In chroot epel7" in ev["what"] or "In chroot fedora20" in ev["what"]

        if "In chroot epel7" in ev["what"]:
            assert_epel7()
            assert_what_from_queue(self.test_q, msg_list=["In chroot fedora20"])
            assert_fedora20()
            assert_what_from_queue(self.test_q, msg_list=["Removing log"])
        else:
            assert_fedora20()
            assert_what_from_queue(self.test_q, msg_list=["Removing log"])
            assert_what_from_queue(self.test_q, msg_list=["In chroot epel7"])
            assert_epel7()

        with pytest.raises(EmptyQueue):
            self.test_q.get_nowait()

        create_repo_expected_call = mock.call(
            username=u'foo',
            projectname=u'bar',
            base_url=u'http://example.com/results/foo/bar/fedora20',
            lock=None,
            path='{}/old_dir/fedora20'.format(self.tmp_dir_name),
            front_url=None
        )
        assert mc_createrepo.call_args == create_repo_expected_call

    @mock.patch("backend.actions.createrepo")
    def test_delete_build_succeeded_createrepo_error(self, mc_createrepo, mc_time):
        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        mc_createrepo.return_value = (1, "", "Create repo failed")
        # mc_createrepo.side_effect = IOError()

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
                "object_type": "build",
                "id": 7,
                "old_value": "old_dir",
                "data": self.ext_data_for_delete_build,
                "object_id": 42,
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )

        test_action.run()
        error_event_recorded = False

        while not self.test_q.empty():
            ev = self.test_q.get_nowait()
            if "Error making local repo" in ev["what"]:
                error_event_recorded = True

        assert error_event_recorded

    @mock.patch("backend.actions.createrepo")
    def test_delete_two_chroots(self, mc_createrepo_unsafe, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796

        """
        mc_createrepo_unsafe.return_value = 0, STDOUT, ""

        resource_name = "1171796.tar.gz"
        self.unpack_resource(resource_name)

        chroot_20_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-x86_64")

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "pkgs": "rubygem-log4r-1.1.10-2.fc21.src.rpm",
                    "username": "foo",
                    "projectname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=self.tmp_dir_name,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.log"))

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))

        assert not os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert not os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))

    @mock.patch("backend.actions.createrepo")
    def test_delete_two_chroots_two_remains(self, mc_createrepo_unsafe, mc_time):
        """
        Regression test, https://bugzilla.redhat.com/show_bug.cgi?id=1171796
        extended: we also put two more chroots, which should be unaffected
        """
        mc_createrepo_unsafe.return_value = 0, STDOUT, ""

        resource_name = "1171796_doubled.tar.gz"
        self.unpack_resource(resource_name)

        chroot_20_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-x86_64")
        chroot_21_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-x86_64")
        chroot_20_i386_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-20-i386")
        chroot_21_i386_path = os.path.join(self.tmp_dir_name, "old_dir", "fedora-21-i386")

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.log"))

        assert os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.rsync.log"))

        assert os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_20_i386_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_i386_path, "rubygem-log4r-1.1.10-2.fc21"))

        mc_time.time.return_value = self.test_time
        mc_front_cb = MagicMock()

        test_action = Action(
            action={
                "action_type": ActionType.DELETE,
                "object_type": "build",
                "object_id": 15,
                "id": 15,
                "old_value": "old_dir",
                "data": json.dumps({
                    "pkgs": "rubygem-log4r-1.1.10-2.fc21.src.rpm",
                    "username": "foo",
                    "projectname": "bar",
                    "chroots": ["fedora-20-x86_64", "fedora-21-x86_64"]
                }),
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=self.tmp_dir_name,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.log"))

        assert not os.path.exists(os.path.join(chroot_20_path, "build-15.rsync.log"))
        assert not os.path.exists(os.path.join(chroot_21_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_20_i386_path, "build-15.rsync.log"))
        assert os.path.exists(os.path.join(chroot_21_i386_path, "build-15.rsync.log"))

        assert not os.path.isdir(os.path.join(chroot_20_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert not os.path.isdir(os.path.join(chroot_21_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_20_i386_path, "rubygem-log4r-1.1.10-2.fc21"))
        assert os.path.isdir(os.path.join(chroot_21_i386_path, "rubygem-log4r-1.1.10-2.fc21"))

    @mock.patch("backend.actions.createrepo_unsafe")
    def test_delete_two_chroots_two_builds_stay_untouched(self, mc_createrepo_unsafe, mc_time):
        # TODO: prepare archive
        """
        Before: 2 builds of the same package-version, all using different chroot
        """
        pass

    @mock.patch("backend.actions.createrepo_unsafe")
    def test_handle_createrepo_ok(self, mc_createrepo_unsafe, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo_unsafe.return_value = 0, STDOUT, ""

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        test_action = Action(
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 8
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 8
        assert result_dict["result"] == ActionResult.SUCCESS

        exp_call_1 = mock.call(lock=None, path=tmp_dir + u'/foo/bar/epel-6-i386')
        exp_call_2 = mock.call(lock=None, path=tmp_dir + u'/foo/bar/fedora-20-x86_64')
        assert exp_call_1 in mc_createrepo_unsafe.call_args_list
        assert exp_call_2 in mc_createrepo_unsafe.call_args_list
        assert len(mc_createrepo_unsafe.call_args_list) == 2


    @mock.patch("backend.actions.createrepo_unsafe")
    def test_handle_createrepo_failure_1(self, mc_createrepo_unsfe, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo_unsfe.return_value = 1, STDOUT, ""

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        test_action = Action(
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 9
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 9
        assert result_dict["result"] == ActionResult.FAILURE

    @mock.patch("backend.actions.createrepo_unsafe")
    def test_handle_createrepo_failure_2(self, mc_createrepo_unsfe, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo_unsfe.return_value = 0, STDOUT, STDERR

        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        test_action = Action(
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 10
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 10
        assert result_dict["result"] == ActionResult.FAILURE

    @mock.patch("backend.actions.createrepo_unsafe")
    def test_handle_createrepo_failure_3(self, mc_createrepo_unsfe, mc_time):
        mc_front_cb = MagicMock()
        tmp_dir = self.make_temp_dir()
        mc_createrepo_unsfe.side_effect = [
            (0, STDOUT, ""),
            (1, STDOUT, STDERR),
        ]


        action_data = json.dumps({
            "chroots": ["epel-6-i386", "fedora-20-x86_64"],
            "username": "foo",
            "projectname": "bar"
        })
        test_action = Action(
            action={
                "action_type": ActionType.CREATEREPO,
                "data": action_data,
                "id": 10
            },
            events=self.test_q, lock=None,
            frontend_callback=mc_front_cb,
            destdir=tmp_dir,
            front_url=None,
            results_root_url=RESULTS_ROOT_URL
        )
        test_action.run()

        result_dict = mc_front_cb.update.call_args[0][0]["actions"][0]

        assert result_dict["id"] == 10
        assert result_dict["result"] == ActionResult.FAILURE
