import os
import json
import logging
import tempfile
import shutil

import testlib
from testlib import assert_logs_exist, AsyncCreaterepoRequestFactory

from copr_common.redis_helpers import get_redis_connection
from copr_backend.createrepo import (
    BatchedCreaterepo,
    MAX_IN_BATCH,
)

from copr_backend.helpers import BackendConfigReader

# pylint: disable=attribute-defined-outside-init


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

    def _prep_batched_repo(self, some_dir, full=False, add=None, delete=None, rpms_to_remove=None):
        self.bcr = BatchedCreaterepo(
            some_dir,
            full,
            add if add is not None else ["subdir_add_1", "subdir_add_2"],
            delete if delete is not None else ["subdir_del_1", "subdir_del_2"],
            rpms_to_remove if rpms_to_remove is not None else [],
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
            "rpms_to_remove": [],
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
                                 set(["del_1", "del_2"]),
                                 set([]))
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
        assert bcr.options() == (False, set(["add_1"]), set(), set())
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
        assert bcr.options() == (False, set(["add_1"]), set(), set())
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

        assert bcr.options() == (False, {"add_1"}, {"del_1"}, set())
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

        assert bcr.options() == (True, set(), {"del_1"}, set())
        assert len(bcr.notify_keys) == 3

    def test_batched_createrepo_task_limit(self, caplog):
        some_dir = "/some/dir/name:pr:limit"

        # request a createrepo run (devel == False!)
        bcr = self._prep_batched_repo(some_dir)
        key = bcr.make_request()
        assert len(self.redis.keys()) == 1

        # add 'add_1' task
        self.request_createrepo.get(some_dir)

        # another background, not considered because devel == True
        self.request_createrepo.get(some_dir, {"add": ["add_2"], "devel": True})

        # Fill-up the MAX_IN_BATCH quota with background requests, and add
        # two more.
        for i in range(3, 3 + MAX_IN_BATCH):
            add_dir = "add_{}".format(i)
            self.request_createrepo.get(some_dir, {"add": [add_dir]})

        # MAX_IN_BATCH + 2 more above + one is ours
        assert len(self.redis.keys()) == MAX_IN_BATCH + 2 + 1

        # Nobody processed us, drop us from DB
        assert not bcr.check_processed()
        assert len(self.redis.keys()) == MAX_IN_BATCH + 2

        # What directories should be processed at once?  Drop add_2 as it is
        # devel=True.
        expected = {"add_{}".format(i) for i in range(1, MAX_IN_BATCH + 3)}
        expected.remove("add_2")
        assert len(expected) == MAX_IN_BATCH + 1

        full, add, remove, rpms_to_remove = bcr.options()
        assert (full, remove, rpms_to_remove) == (False, set(), set())
        # check that the batch is this request + (MAX_IN_BATCH - 1)
        assert len(add) == MAX_IN_BATCH - 1

        # The redis.keys() list isn't sorted, and even if it was - our own
        # PID in the key would make the final order.  Therefore we don't know
        # which items are skipped, but we know there are two left for the next
        # batch.
        assert len(expected-add) == 2

        # Nothing unexpected should go here.
        assert add-expected == set()

        assert len(bcr.notify_keys) == MAX_IN_BATCH - 1
        assert self.redis.hgetall(key) == {}

        log_entries_expected = {
            "Batch copr-repo limit",
            "Has already a status? False",
        }

        msg_count = len(caplog.record_tuples)
        if msg_count == 3:
            # we have one miss in roughly MAX_IN_BATCH tasks in the redis
            # database, so there's roughly 1:MAX_IN_BATCH chance this message
            # doesn't appear.
            log_entries_expected.add("'devel' attribute doesn't match")
        else:
            assert msg_count == 2

        assert_logs_exist(log_entries_expected, caplog)

        bcr.commit()
        without_status = set()
        for key in self.redis.keys():
            if not self.redis.hget(key, "status"):
                data = json.loads(self.redis.hget(key, "task"))
                for add_dir in data["add"]:
                    without_status.add(add_dir)
        assert "add_2" in without_status
        assert len(without_status) == 3
