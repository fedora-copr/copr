import time
from datetime import datetime, timedelta
import pytest
import coprs
from copr_common.enums import StatusEnum
from coprs.helpers import ChrootDeletionStatus
from tests.coprs_test_case import CoprsTestCase, new_app_context


class TestBuildModel(CoprsTestCase):

    def test_get_chroots_by_status(self, f_users, f_coprs,
                                   f_builds, f_mock_chroots,
                                   f_mock_chroots_many, f_build_many_chroots, f_db):

        self.db.session.commit()

        expected_on_none = set([ch_name for ch_name, status in self.status_by_chroot.items()])
        result_on_none = set([ch.name for ch in self.b_many_chroots.get_chroots_by_status()])
        assert result_on_none == expected_on_none

        expected_1 = set([ch_name for ch_name, status in self.status_by_chroot.items()
                          if status in [0, 1, 3]])

        result_1 = set([ch.name for ch in self.b_many_chroots.get_chroots_by_status(statuses=[0, 1, 3])])
        assert expected_1 == result_1


    @pytest.mark.usefixtures("f_users", "f_coprs", "f_builds",
                             "f_mock_chroots_many", "f_pr_dir", "f_db")
    def test_chroot_denylist(self):
        # test main package
        assert len(list(self.p1.chroots)) == 15
        self.p1.chroot_denylist_raw = '*-19-*, epel*'
        assert len(self.p1.chroot_denylist) == 2
        assert len(list(self.p1.chroots)) == 8

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_builds",
                             "f_mock_chroots_many", "f_pr_dir", "f_db")
    def test_chroot_denylist_all(self):
        assert len(list(self.p1.chroots)) == 15
        assert len(list(self.p1.copr.active_chroots)) == 15
        self.p1.chroot_denylist_raw = '*'
        # even though we blacklised (by mistake) all chroots, package builds
        # against all chroots (fallback)
        assert len(list(self.p1.chroots)) == 15

    def test_finished(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.b1.build_chroots[0].status = StatusEnum("pending")
        assert not self.b1.finished

        self.b1.build_chroots[0].status = StatusEnum("succeeded")
        assert self.b1.finished

        self.b1.build_chroots[0].status = StatusEnum("running")
        assert not self.b1.finished

        self.b1.build_chroots[0].status = StatusEnum("failed")
        assert self.b1.finished

    def test_finished_srpms(self, f_users, f_coprs, f_builds, f_db):
        assert not self.b1.build_chroots

        self.b1.source_status = StatusEnum("running")
        assert not self.b1.finished
        assert not self.b1.finished_early

        self.b1.source_status = StatusEnum("canceled")
        assert self.b1.finished
        assert self.b1.finished_early

        self.b1.source_status = StatusEnum("failed")
        assert self.b1.finished
        assert self.b1.finished_early

    @pytest.mark.usefixtures('f_users', 'f_coprs', 'f_mock_chroots', 'f_builds',
                             'f_db')
    def test_canceled(self):
        """ test that build.cancel affects build.build_chroots[*].finished """
        bch = self.b1.build_chroots[0]
        bch.status = StatusEnum("pending")
        assert not self.b1.finished
        assert not bch.finished
        self.b1.canceled = True
        assert bch.finished
        self.b1.canceled = False
        self.b1.source_status = StatusEnum("canceled")
        assert bch.finished

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_build_logs(self):
        config = coprs.app.config
        config["COPR_DIST_GIT_LOGS_URL"] = "http://example-dist-git/url"

        # no matter state,  result_dir none implies log None
        self.b1.result_dir = None
        assert self.b1.source_live_log_url is None
        assert self.b1.source_backend_log_url is None

        def _pfxd(basename):
            pfx = ("http://copr-be-dev.cloud.fedoraproject.org/results/"
                   "user1/foocopr/srpm-builds/00000001")
            return "/".join([pfx, basename])

        # pending state
        self.b1.source_status = StatusEnum("pending")
        assert self.b1.source_live_log_url is None
        assert self.b1.source_backend_log_url is None

        # starting state
        self.b1.result_dir = "001"
        self.b1.source_status = StatusEnum("starting")
        assert self.b1.source_live_log_url is None
        assert self.b1.source_backend_log_url == _pfxd("backend.log")

        # running state
        self.b1.source_status = StatusEnum("running")
        assert self.b1.source_live_log_url == _pfxd("builder-live.log")
        assert self.b1.source_backend_log_url == _pfxd("backend.log")

        # importing state
        self.b1.submitted_on = int(time.time()) - 24*3600
        self.b1.source_status = StatusEnum("importing")
        assert self.b1.get_source_log_urls == [
            _pfxd("builder-live.log.gz"),
            _pfxd("backend.log.gz"),
            "http://example-dist-git/url/1.log",
        ]

        for state in ["failed", "succeeded", "canceled", "importing"]:
            self.b1.source_status = StatusEnum(state)
            assert self.b1.source_live_log_url == _pfxd("builder-live.log.gz")
            assert self.b1.source_backend_log_url == _pfxd("backend.log.gz")

        for state in ["skipped", "forked", "waiting", "unknown"]:
            self.b1.source_status = StatusEnum(state)
            assert self.b1.source_live_log_url is None
            assert self.b1.source_backend_log_url is None

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_buildchroot_logs(self):
        build = self.b1_bc[0]

        # no matter state,  result_dir none implies log None
        build.result_dir = None
        assert build.rpm_live_log_url is None
        assert build.rpm_backend_log_url is None

        def _pfxd(basename):
            pfx = ("http://copr-be-dev.cloud.fedoraproject.org/results/"
                   "user1/foocopr/fedora-18-x86_64/bar")
            return "/".join([pfx, basename])

        # pending state
        build.status = StatusEnum("pending")
        assert build.rpm_live_log_url is None
        assert build.rpm_backend_log_url is None

        # starting state
        build.result_dir = "bar"
        build.status = StatusEnum("starting")
        assert build.rpm_live_log_url is None
        assert build.rpm_backend_log_url == _pfxd("backend.log")

        # running state
        build.status = StatusEnum("running")
        assert build.rpm_live_logs == [
            _pfxd("backend.log"),
            _pfxd("builder-live.log"),
        ]

        for state in ["failed", "succeeded", "canceled"]:
            build.status = StatusEnum(state)
            assert build.rpm_live_log_url == _pfxd("builder-live.log.gz")
            assert build.rpm_backend_log_url == _pfxd("backend.log.gz")

        for state in ["skipped", "forked", "waiting", "unknown"]:
            build.status = StatusEnum(state)
            assert build.rpm_live_log_url is None
            assert build.rpm_backend_log_url is None

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds")
    def test_source_state_translation(self):
        """ test the very old builds that don't have the source_status set """
        self.b1.source_status = None
        assert self.b1.source_state == "unknown"
        self.b1.source_status = 0
        assert self.b1.source_state == "failed"


class TestCoprModel(CoprsTestCase):

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_permissible_chroots(self):
        """
        Test for what chroots we want to show repofiles in the project overview
        """
        assert len(self.c2.mock_chroots) == 2
        mc1 = self.c2.mock_chroots[0]
        mc2 = self.c2.mock_chroots[1]
        chroot = self.c2.copr_chroots[0]

        # Normal, active chroot
        assert chroot.delete_status == ChrootDeletionStatus("active")
        assert self.c2.enable_permissible_chroots == [mc1, mc2]

        # Chroot is deactivated
        chroot.mock_chroot.is_active = False
        assert chroot.delete_status == ChrootDeletionStatus("deactivated")
        assert self.c2.enable_permissible_chroots == [mc2]

        # Chroot is EOLed
        chroot.delete_after = datetime.now() + timedelta(days=180)
        chroot.delete_notify = datetime.now()
        assert chroot.delete_status == ChrootDeletionStatus("preserved")
        assert self.c2.enable_permissible_chroots == [mc1, mc2]

        # After the preservation period is gone
        chroot.delete_after = datetime.now() - timedelta(days=1)
        assert chroot.delete_status == ChrootDeletionStatus("expired")
        assert self.c2.enable_permissible_chroots == [mc2]
