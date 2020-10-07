"""
Tests for working with Batches
"""

import pytest
from copr_common.enums import StatusEnum
from coprs import models
from coprs.exceptions import BadRequest
from coprs.logic.batches_logic import BatchesLogic
from tests.coprs_test_case import CoprsTestCase


@pytest.mark.usefixtures("f_u1_ts_client", "f_mock_chroots", "f_db")
class TestBatchesLogic(CoprsTestCase):
    batches = None

    def _prepare_project_with_batches(self):
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
