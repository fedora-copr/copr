"""
Tests for 'alter-chroot' command, specifically EOL handling of pending builds.
"""

import json

import pytest
from copr_common.enums import StatusEnum
from tests.coprs_test_case import CoprsTestCase
from commands.alter_chroot import func_alter_chroot


class TestAlterChrootEOL(CoprsTestCase):

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_cancels_pending_build_chroots(self):
        for bch in self.b3_bc:
            bch.status = StatusEnum("pending")
        self.db.session.commit()

        chroot_name = self.b3_bc[0].mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        for bch in self.b3_bc:
            self.db.session.refresh(bch)
            if bch.mock_chroot.name == chroot_name:
                assert bch.status == StatusEnum("canceled")
                assert "EOLed" in bch.status_reason

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_creates_cancel_request_for_running(self):
        bch = self.b3_bc[0]
        bch.status = StatusEnum("running")
        self.db.session.commit()

        chroot_name = bch.mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        cancel_requests = self.models.CancelRequest.query.all()
        task_ids = [cr.what for cr in cancel_requests]
        assert bch.task_id in task_ids

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_skips_finished_build_chroots(self):
        bch = self.b4_bc[0]
        bch.status = StatusEnum("succeeded")
        self.db.session.commit()

        chroot_name = bch.mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        self.db.session.refresh(bch)
        assert bch.status == StatusEnum("succeeded")

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eoled_chroot_not_in_pending_jobs(self):
        for bch in self.b3_bc:
            bch.status = StatusEnum("pending")
        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/")
        data = json.loads(r.data.decode("utf-8"))
        build_ids_before = [j["build_id"] for j in data]
        assert self.b3.id in build_ids_before

        chroot_name = self.b3_bc[0].mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        r = self.tc.get("/backend/pending-jobs/")
        data = json.loads(r.data.decode("utf-8"))
        for job in data:
            if job["build_id"] == self.b3.id:
                assert job["chroot"] != chroot_name

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_then_backend_reports_ok(self):
        """
        Backend finished the build before processing the cancel request
        and reports succeeded — the chroot must stay canceled.
        """
        bch = self.b3_bc[0]
        bch.status = StatusEnum("running")
        self.db.session.commit()

        chroot_name = bch.mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        assert bch.status == StatusEnum("canceled")

        self.backend_report_build_end(
            self.b3, chroot_name, StatusEnum("succeeded"))

        self.db.session.refresh(bch)
        assert bch.status == StatusEnum("canceled")

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_cancel_then_backend_confirms(self):
        """
        Backend processes the CancelRequest — status stays canceled
        and CancelRequest is cleaned up.
        """
        bch = self.b3_bc[0]
        bch.status = StatusEnum("running")
        self.db.session.commit()

        chroot_name = bch.mock_chroot.name
        task_id = bch.task_id
        func_alter_chroot([chroot_name], "eol")

        cancel_requests = self.models.CancelRequest.query.all()
        assert any(cr.what == task_id for cr in cancel_requests)

        r = self.tc.post(
            f"/backend/build-tasks/canceled/{task_id}/",
            content_type="application/json",
            headers=self.auth_header,
            data=json.dumps(True),
        )
        assert r.status_code == 200

        self.db.session.refresh(bch)
        assert bch.status == StatusEnum("canceled")

        cancel_requests = self.models.CancelRequest.query.all()
        assert not any(cr.what == task_id for cr in cancel_requests)

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_eol_does_not_set_build_canceled_flag(self):
        """
        EOL cancels individual chroots but Build.canceled must stay
        False so that other chroots of the same build are unaffected.
        """
        for bch in self.b3_bc:
            bch.status = StatusEnum("pending")
        self.db.session.commit()

        chroot_name = self.b3_bc[0].mock_chroot.name
        func_alter_chroot([chroot_name], "eol")

        self.db.session.refresh(self.b3)
        assert self.b3.canceled is False
