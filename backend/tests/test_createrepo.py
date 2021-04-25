import os
import copy
import json
import logging
import tarfile
import tempfile
import shutil
import time
import pytest

from unittest import mock
from unittest.mock import MagicMock

from copr_backend.createrepo import (
    BatchedCreaterepo,
    createrepo,
    createrepo_unsafe,
    MAX_IN_BATCH,
    run_cmd_unsafe,
)

from copr_backend.helpers import BackendConfigReader, get_redis_connection
from copr_backend.exceptions import CreateRepoError

import testlib
from testlib import assert_logs_exist, AsyncCreaterepoRequestFactory

# pylint: disable=attribute-defined-outside-init

@mock.patch('copr_backend.createrepo.createrepo_unsafe')
@mock.patch('copr_backend.createrepo.add_appdata')
def test_createrepo_conditional_true(mc_add_appdata, mc_create_unsafe):
    mc_create_unsafe.return_value = ""
    mc_add_appdata.return_value = ""

    createrepo(path="/tmp/", username="foo", projectname="bar")
    mc_create_unsafe.reset_mock()

    createrepo(path="/tmp/", username="foo", projectname="bar")
    mc_create_unsafe.reset_mock()


@mock.patch('copr_backend.createrepo.createrepo_unsafe')
def test_createrepo_conditional_false(mc_create_unsafe):
    base_url = "http://example.com/repo/"
    createrepo(path="/tmp/", username="foo", projectname="bar", base_url=base_url, devel=True)
    assert mc_create_unsafe.call_args == mock.call('/tmp/', dest_dir='devel', base_url=base_url)


@pytest.yield_fixture
def mc_popen():
    with mock.patch('copr_backend.createrepo.Popen') as handle:
        yield handle


@pytest.yield_fixture
def mc_run_cmd_unsafe():
    with mock.patch('copr_backend.createrepo.run_cmd_unsafe') as handle:
        yield handle


class TestCreaterepo(object):
    def setup_method(self, method):
        self.tmp_dir_name = self.make_temp_dir()
        self.test_time = time.time()
        self.base_url = "http://example.com/repo/"

        self.username = "foo"
        self.projectname = "bar"

    # def unpack_resource(self, resource_name):
    #     if self.tmp_dir_name is None:
    #         self.make_temp_dir()
    #
    #     src_path = os.path.join(os.path.dirname(__file__),
    #                             "_resources", resource_name)
    #
    #     with tarfile.open(src_path, "r:gz") as tfile:
    #         tfile.extractall(os.path.join(self.tmp_dir_name, "old_dir"))

    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)
        os.mkdir(self.tmp_dir_name)
        return self.tmp_dir_name

    #def test_add_appdata(self, mc_run_cmd_unsafe):
    #    todo: implement, need to test behaviour with/withou produced appstream files
    #    for lock in [None, MagicMock()]:
    #        add_appdata(self.tmp_dir_name, self.username, self.projectname, lock=lock)
    #        print mc_run_cmd_unsafe.call_args_list
    #        mc_run_cmd_unsafe.reset()

    def test_run_cmd_unsafe_ok(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.return_value.communicate.return_value = ("stdout", "stderr")
        mc_popen.return_value.returncode = 0

        assert run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"
        mc_popen.reset()

    def test_run_cmd_unsafe_err_popen(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.side_effect = IOError()

        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_run_cmd_unsafe_err_return_code(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.return_value.communicate.return_value = ("stdout", "stderr")
        mc_popen.return_value.returncode = 1


        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert err.value.stdout == "stdout"
        assert err.value.stderr == "stderr"
        assert err.value.exit_code == 1
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_run_cmd_unsafe_err_communicate(self, mc_popen):
        cmd = "foo --bar"
        mc_handle = MagicMock()
        mc_popen.return_value = MagicMock()
        mc_handle.returncode = 0
        mc_handle.side_effect = RuntimeError()

        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_createrepo_generated_commands_existing_repodata(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ('/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 '
                           '--update -s sha --checksum md5 ' + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ('/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 '
                           '--update ' + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path)
            assert mc_run_cmd_unsafe.call_args[0][0] == expected

    def test_createrepo_generated_commands_comps_xml(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        for path in [path_epel_5, path_fedora]:
            for add_comps in [True, False]:
                os.makedirs(path)

                comps_path = os.path.join(path, "comps.xml")
                if add_comps:
                    with open(comps_path, "w") as handle:
                        handle.write("1")

                repo_path = os.path.join(path, "repodata")
                os.makedirs(repo_path)
                with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                    handle.write("1")

                createrepo_unsafe(path)
                if add_comps:
                    assert "--groupfile" in mc_run_cmd_unsafe.call_args[0][0]
                else:
                    assert "--groupfile" not in mc_run_cmd_unsafe.call_args[0][0]
                mc_run_cmd_unsafe.mock_reset()
                shutil.rmtree(path, ignore_errors=True)

    def test_createrepo_devel_generated_commands_existing_repodata(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "-s sha --checksum md5 "
                           "--outputdir " + os.path.join(path_epel_5, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "--outputdir " + os.path.join(path_fedora, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "devel", "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert mc_run_cmd_unsafe.call_args[0][0] == expected

    def test_createrepo_devel_generated_commands(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "-s sha --checksum md5 "
                           "--outputdir " + os.path.join(path_epel_5, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "--outputdir " + os.path.join(path_fedora, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert os.path.exists(os.path.join(path, "devel"))
            assert mc_run_cmd_unsafe.call_args[0][0] == expected
            # assert mc_popen.call_args == mock.call(expected, stderr=-1, stdout=-1)

    def test_createrepo_devel_creates_folder(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")

        for path in [path_epel_5, path_fedora]:
            os.makedirs(path)

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert os.path.exists(os.path.join(path, "devel"))


class TestBatchedCreaterepo:
    def setup_method(self):
        self.workdir = tempfile.mkdtemp(prefix="copr-batched-cr-test-")
        self.config_file = testlib.minimal_be_config(self.workdir, {
            "redis_db": 9,
            "redis_port": 7777,
        })
        self.config = BackendConfigReader(self.config_file).read()
        self.redis = get_redis_connection(self.config)
        self.request_createrepo = AsyncCreaterepoRequestFactory(self.redis)
        self.redis.flushdb()
        self._pid = os.getpid()

    def teardown_method(self):
        shutil.rmtree(self.workdir)
        self.redis.flushdb()

    def _prep_batched_repo(self, some_dir, full=False, add=None, delete=None):
        self.bcr = BatchedCreaterepo(
            some_dir,
            full,
            add if add is not None else ["subdir_add_1", "subdir_add_2"],
            delete if delete is not None else ["subdir_del_1", "subdir_del_2"],
            logging.getLogger(),
            backend_opts=self.config,
        )
        return self.bcr

    def test_batched_createrepo_normal(self):
        some_dir = "/some/dir/name:pr:135"
        bcr = self._prep_batched_repo(some_dir)
        bcr.make_request()

        keys = self.redis.keys()
        assert len(keys) == 1
        assert keys[0].startswith("createrepo_batched::{}::".format(some_dir))
        redis_dict = self.redis.hgetall(keys[0])
        redis_task = json.loads(redis_dict["task"])
        assert len(redis_dict) == 1
        assert redis_task == {
            "appstream": True,
            "devel": False,
            "add": ["subdir_add_1", "subdir_add_2"],
            "delete": ["subdir_del_1", "subdir_del_2"],
            "full": False,
        }
        self.request_createrepo.get(some_dir)
        # appstream=False has no effect, others beat it, appstream=False
        # makes it non-matching.
        self.request_createrepo.get(some_dir, {"add": ["add_2"], "appstream": False})
        self.request_createrepo.get(some_dir, {"add": [], "delete": ["del_1"]})
        self.request_createrepo.get(some_dir, {"add": [], "delete": ["del_2"]})
        assert not bcr.check_processed()
        assert bcr.options() == (False,
                                 set(["add_1"]),
                                 set(["del_1", "del_2"]))
        assert len(bcr.notify_keys) == 3

        our_key = keys[0]

        bcr.commit()
        keys = self.redis.keys()
        count_non_finished = 0
        for key in keys:
            assert key != our_key
            task_dict = self.redis.hgetall(key)
            if "status" in task_dict:
                assert task_dict["status"] == "success"
            else:
                count_non_finished += 1
        assert count_non_finished == 1


    def test_batched_createrepo_already_done(self):
        some_dir = "/some/dir/name"
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()
        self.request_createrepo.get(some_dir)
        self.redis.hset(key, "status", "success")
        assert bcr.check_processed()
        assert self.redis.hgetall(key) == {}
        assert bcr.notify_keys == []  # nothing to commit()

    def test_batched_createrepo_other_already_done(self, caplog):
        some_dir = "/some/dir/name:pr:3"
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()

        # create two other requests, one is not to be processed
        self.request_createrepo.get(some_dir)
        self.request_createrepo.get(some_dir, {"add": ["add_2"]}, done=True)

        # nobody processed us
        assert not bcr.check_processed()

        # we only process the first other request
        assert bcr.options() == (False, set(["add_1"]), set())
        assert len(bcr.notify_keys) == 1  # still one to notify
        assert self.redis.hgetall(key) == {}
        assert len(caplog.record_tuples) == 2
        assert_logs_exist("already processed, skip", caplog)

    def test_batched_createrepo_devel_mismatch(self, caplog):
        some_dir = "/some/dir/name:pr:5"
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()

        # create two other requests, one is not to be processed
        self.request_createrepo.get(some_dir, {"add": ["add_2"], "devel": True})
        self.request_createrepo.get(some_dir)

        # nobody processed us
        assert not bcr.check_processed()

        # we only process the first other request
        assert bcr.options() == (False, set(["add_1"]), set())
        assert len(bcr.notify_keys) == 1  # still one to notify
        assert self.redis.hgetall(key) == {}
        assert len(caplog.record_tuples) == 2
        assert_logs_exist("'devel' attribute doesn't match", caplog)

    def test_batched_createrepo_full_we_take_others(self):
        some_dir = "/some/dir/name:pr:take_others"
        bcr = self._prep_batched_repo(some_dir, full=True, add=[], delete=[])
        key = bcr.make_request()

        task = self.redis.hgetall(key)
        task_json = json.loads(task["task"])
        assert task_json["full"]
        assert task_json["add"] == [] == task_json["delete"]

        # create three other requests, one is not to be processed
        self.request_createrepo.get(some_dir, {"add": ["add_2"], "devel": True})
        self.request_createrepo.get(some_dir)
        self.request_createrepo.get(some_dir, {"add": [], "delete": ["del_1"]})

        assert len(self.redis.keys()) == 4
        assert not bcr.check_processed()
        assert len(self.redis.keys()) == 3

        assert bcr.options() == (False, {"add_1"}, {"del_1"})
        assert len(bcr.notify_keys) == 2

    def test_batched_createrepo_full_others_take_us(self):
        some_dir = "/some/dir/name:pr:others_take_us"
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()
        task = self.redis.hgetall(key)
        task_json = json.loads(task["task"])
        assert not task_json["full"]
        assert not bcr.check_processed()

        # create four other requests, one is not to be processed
        self.request_createrepo.get(some_dir, {"add": ["add_2"]})
        self.request_createrepo.get(some_dir, done=True)
        self.request_createrepo.get(some_dir, {"add": [], "delete": [], "full": True})
        self.request_createrepo.get(some_dir, {"add": [], "delete": ["del_1"]})

        assert bcr.options() == (True, set(), {"del_1"})
        assert len(bcr.notify_keys) == 3

    def test_batched_createrepo_task_limit(self, caplog):
        some_dir = "/some/dir/name:pr:limit"
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()

        # create limit +2 other requests, one is not to be processed, once
        # skipped
        self.request_createrepo.get(some_dir)
        self.request_createrepo.get(some_dir, {"add": ["add_2"], "devel": True})
        for i in range(3, 3 + MAX_IN_BATCH):
            add_dir = "add_{}".format(i)
            self.request_createrepo.get(some_dir, {"add": [add_dir]})

        # nobody processed us
        assert not bcr.check_processed()

        expected = {"add_{}".format(i) for i in range(1, MAX_IN_BATCH + 2)}
        expected.remove("add_2")
        assert len(expected) == MAX_IN_BATCH

        full, add, remove = bcr.options()
        assert (full, remove) == (False, set())
        assert len(add) == MAX_IN_BATCH

        # The redis.keys() isn't sorted, and even if it was - PID would make the
        # order.  Therefore we don't know which one is skipped, but only one is.
        assert len(add - expected) == 1
        assert len(expected - add) == 1

        assert len(bcr.notify_keys) == MAX_IN_BATCH
        assert self.redis.hgetall(key) == {}
        assert len(caplog.record_tuples) == 3
        assert_logs_exist({
            "'devel' attribute doesn't match",
            "Batch copr-repo limit",
            "Checking if we have to start actually",
        }, caplog)
