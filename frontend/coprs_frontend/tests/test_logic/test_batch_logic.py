"""
Tests for working with Batches
"""

import json
import time
import pytest
from flask_sqlalchemy import get_debug_queries
from copr_common.enums import StatusEnum
from coprs import app, models
from coprs.exceptions import BadRequest
from coprs.logic.batches_logic import BatchesLogic
from tests.coprs_test_case import CoprsTestCase


@pytest.mark.usefixtures("f_u1_ts_client", "f_mock_chroots", "f_db")
class TestBatchesLogic(CoprsTestCase):
    batches = None

    def _prepare_project_with_batches(self, more=None):
        """
        [1, 3] <= [2, 4] (<= [5] ... per "more")
        """
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])
        assert models.Copr.query.count() == 1
        self.api3.submit_url_build("test")
        self.web_ui.submit_url_build("test", build_options={
            "after_build_id": 1,
        })
        self.api3.submit_url_build("test", build_options={
            "with_build_id": 1,
        })
        self.web_ui.submit_url_build("test", build_options={
            "with_build_id": 2,
        })
        self.batches = batches = models.Batch.query.all()
        assert len(batches) == 2
        for batch in batches:
            assert len(batch.builds) == 2

        if not more:
            return

        self.web_ui.create_distgit_package("test", "testpkg")

        # submit two more batches for that package ^^
        for i in range(more):
            after_id = i + 4
            self.api3.rebuild_package(
                "test", "testpkg",
                # assure that BuildChroot is pre-generated
                build_options={
                    'chroots': ["fedora-rawhide-i386"],
                    "after_build_id": after_id,
                })

        # Emulate the SRPM upload "resubmit" action - the source_status is
        # succeeded, and all build chroots are pending.  See BuildsLogic.add()
        # and the skip_import argument.  Such BuildChroot is immediately ready
        # to be taken (except that it is blocked by the Batch 2).  It would be
        # nice to train on a real uploaded build here instead, of course.
        self.batches = batches = models.Batch.query.all()
        self.batches[1+more].builds[0].source_status = StatusEnum("succeeded")
        self.batches[1+more].builds[0].build_chroots[0].status = StatusEnum("pending")
        assert len(batches) == 2 + more
        self.db.session.commit()

    def _succeed_first_batch(self):
        for build in self.batches[0].builds:
            build.source_status = StatusEnum("succeeded")
            for chroot in build.build_chroots:
                chroot.state = StatusEnum("succeeded")
            assert build.finished
        assert self.batches[0].finished
        self.db.session.commit()

    def _submit(self, build_options, status=400):
        resp = self.api3.submit_url_build("test", build_options=build_options)
        assert resp.status_code == status
        return resp.data.decode("utf-8")

    def test_normal_batch_operation_failures(self):
        self._prepare_project_with_batches()
        self._succeed_first_batch()

        # we can not assign builds to finished builds
        error = self._submit({"with_build_id": 1})
        assert "Batch 1 is already finished" in error

        # we can not assign builds to non-existing builds, and try spaces
        # around numbers, too
        error = self._submit({"with_build_id": ' 6 '})
        assert "Build 6 not found" in error

        # both batch options
        error = self._submit({"with_build_id": 1, "after_build_id": 2})
        assert "Only one batch option" in error

        # invalid int
        error = self._submit({"with_build_id": "None"})
        assert "Not a valid integer" in error

        # drop the finished build from batch
        build = models.Build.query.get(1)
        build.batch = None
        self.db.session.commit()
        error = self._submit({"with_build_id": 1})
        assert "new batch can not be created" in error
        assert "already finished" in error

    def test_less_likely_batch_problems(self):
        self._prepare_project_with_batches()
        # non existing build
        with pytest.raises(BadRequest) as error:
            BatchesLogic.get_batch_or_create(7, self.transaction_user)
        assert "doesn't exist" in str(error)
        # existing build
        BatchesLogic.get_batch_or_create(2, self.transaction_user)
        # permission problem
        user = models.User.query.get(2)
        with pytest.raises(BadRequest) as error:
            BatchesLogic.get_batch_or_create(2, user, modify=True)
        assert "The batch 2 belongs to project user1/test" in str(error)
        assert "You are not allowed to build there" in str(error)

    def test_cant_group_others_build(self):
        self._prepare_project_with_batches()
        # de-assign the build from batch
        build = models.Build.query.get(1)
        build.batch = None
        self.db.session.commit()

        user = models.User.query.get(2)
        with pytest.raises(BadRequest) as error:
            BatchesLogic.get_batch_or_create(1, user, modify=True)
        assert "Build 1 is not yet in any batch" in str(error)
        assert "'user2' doesn't have the build permissions" in str(error)

    def test_batched_build_queue_sql_performance(self):
        more_bchs = 5
        with app.app_context():
            self._prepare_project_with_batches(more=more_bchs)
            self._succeed_first_batch()

        with app.app_context():
            r = self.tc.get("/backend/pending-jobs/")
            data = json.loads(r.data.decode("utf-8"))
            dq = get_debug_queries()

        # Be very careful if you have to bump the number here.  Any O(N)
        # slowdown means huge penalty on /bakcend/pending-jobs/ route.
        #
        # 1. Get user1 info (for self.test_client).
        # 2. Large query for Source builds (get_pending_srpm_build_tasks).
        # 3. Get info about Batch 1 - *expected* (even though it's in "finished"
        #    state and is cached in Redis), this is triggered by lazy-loads from
        #    accessing objects from query 1 => the source builds in the query
        #    are from other batches (e.g. 3), but to check if Batch 3 is blocked
        #    (already loaded) we have to check if Batch 2 is blocked (loaded)
        #    and thus also if Batch 1 is blocked.  Because we ask for
        #    'batch_1.blocked' it needs to be loaded **now** because it is not
        #    yet (it is not loaded because all builds there are already
        #    finished).
        # 4. Read all builds (lazy) from Batch 2 to get Build statuses.  This is
        #    the only Batch where we need to iterate through Builds (as there's
        #    only one tree of batches).
        # 5. Read BuildChroots (lazy) from ^^ to get statuses.
        # 6. Large query for BuildChroots (get_pending_build_tasks).
        #
        # The last batch (ID=2+more_bchs) contains one "ready" BuildChroot task
        # (the srpm upload emulation, see _prepare_project_with_batches()) which
        # is only blocked by parent batch.  But because we cache Batch objects
        # in pending_jobs() method - they are preloaded and we can be sure that
        # we don't have to re-load the batch data to check if that is finished.
        expected = 6
        if expected != len(dq):
            print()
            for n, query in enumerate(dq):
                print("==== query {} ====".format(n))
                print(query)
            print()

        assert len(dq) == expected

        # First batch is done, second is processing and third is blocked.  Only
        # the builds from second batch are present.
        assert data == [{
            'background': False,
            'build_id': 2,
            'chroot': None,
            'project_owner': 'user1',
            'sandbox': 'user1/test--user1',
            'task_id': '2',
        }, {
            'background': False,
            'build_id': 4,
            'chroot': None,
            'project_owner': 'user1',
            'sandbox': 'user1/test--user1',
            'task_id': '4',
        }]

    def _add_one_large_batch(self, projectname, builds=1000, after_build=None):
        # create the first build in batch
        bo = {
            # pre-create two build chroots
            "chroots": ["fedora-rawhide-i386", "fedora-18-x86_64"],
        }
        if after_build:
            bo["after_build_id"] = after_build
        res = self.api3.submit_url_build(projectname, build_options=bo)
        batch_build_id = json.loads(res.data)['items'][0]['id']

        # create the batch by grouping two builds
        res = self.web_ui.submit_url_build(projectname, build_options={
            "with_build_id": batch_build_id,
        })

        self.db.session.commit()

        build = models.Build.query.get(batch_build_id)
        batch = build.batch
        mock_chroot = build.build_chroots[0].mock_chroot

        b_objs = []
        bch_objs = []
        for counter in range(builds-2):
            new_b = models.Build()
            new_b.pkgs = 'https://example.com/some.src.rpm'
            new_b.submitted_on = time.time()
            new_b.source_json = '{"url": "https://example.com/some.src.rpm"}'
            new_b.srpm_url = 'https://example.com/some.src.rpm'
            new_b.batch_id = batch.id
            new_b.canceled = 0
            new_b.copr_dir_id = build.copr_dir_id
            new_b.copr_id = build.copr_id

            new_bch = models.BuildChroot()
            new_bch.build_id = counter + build.id + 2  # two build ready
            new_bch.mock_chroot_id = mock_chroot.id

            if not after_build and not counter % 50:
                # a few builds in the unblocked batch are done
                new_bch.status = StatusEnum("pending")
                new_b.source_status = StatusEnum("succeeded")
                new_b.package_id = 1
            else:
                new_bch.status = StatusEnum("waiting")
                new_b.source_status = StatusEnum("pending")

            b_objs.append(new_b)
            bch_objs.append(new_bch)

        self.db.session.bulk_save_objects(b_objs)
        self.db.session.bulk_save_objects(bch_objs)
        self.db.session.commit()
        return batch_build_id

    def test_large_batch_build_queue(self):
        """
        Fill in few thousands of builds, some of them with build chroots, some
        of them with finished source builds - and measure.  Fail if something
        takes unexpectedly long.
        """
        projects = ["aaa", "bbb", "ccc", "ddd", "eee", "fff"]

        t1 = time.time()
        with app.app_context():
            batches = 4
            for projectname in projects:
                self.web_ui.new_project(projectname,
                                        ["fedora-rawhide-i386", "fedora-18-x86_64"])
                self.web_ui.create_distgit_package(projectname, "testpkg")

                after_build = None
                for _b in range(batches):
                    after_build = self._add_one_large_batch(
                        projectname, after_build=after_build)

        t2 = time.time()
        with app.app_context():
            r = self.tc.get("/backend/pending-jobs/")
            data = json.loads(r.data.decode("utf-8"))
            dq = get_debug_queries()

        t3 = time.time()

        # each project has 1000 unblocked tasks
        assert len(data) == len(projects) * 1000
        # most of the tasks are source builds, but some (each 50th is binary
        # rpm build, aka BuildChroot)
        assert len([d for d in data if d["chroot"]]) == len(projects)*20
        for projectname in projects:
            assert len([d for d in data if projectname+"--" in d["sandbox"]]) == 1000

        fill_time = t2 - t1
        sql_alchemy_time = t3 - t2
        query_time = sum([q.duration for q in dq])

        asserts = [
            sql_alchemy_time < fill_time/3*2,
            query_time < fill_time/20,
            # - for each project two queries (for batch => one build +batch_build)
            # - two large queries (srpm + rpms)
            # - one query for self.tc initialization
            # Note that we only lazily load first Build in each unblocked batch,
            # because even that first Build in batch is not yet finished -
            # meaning that the whole batch is not yet finished as well.
            len(dq) == len(projects)*2 + 2 + 1,
        ]

        if not all(asserts):
            print("fill_time: {}".format(fill_time))
            print("sql_alchemy_time: {}".format(sql_alchemy_time))
            print("query_time: {}".format(query_time))
            for n, query in enumerate(dq):
                print("=== {} ===".format(n))
                print(query)
            assert False
