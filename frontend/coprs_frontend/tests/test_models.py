from copr_common.enums import StatusEnum
from tests.coprs_test_case import CoprsTestCase


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


    def test_chroot_blacklist(self, f_users, f_coprs, f_builds, f_mock_chroots_many, f_pr_dir, f_db):
        # test main package
        assert len(list(self.p1.chroots)) == 15
        self.p1.chroot_blacklist_raw = '*-19-*, epel*'
        assert len(self.p1.chroot_blacklist) == 2
        assert len(list(self.p1.chroots)) == 8

        # non-main package inherits from main package by default
        assert len(list(self.p4.chroots)) == 8

        # but if we set the blacklist here, too, it get's precedence
        self.p4.chroot_blacklist_raw = 'epel*'
        assert len(self.p4.chroot_blacklist) == 1
        assert len(list(self.p4.chroots)) == 10

    def test_chroot_blacklist_all(self, f_users, f_coprs, f_builds, f_mock_chroots_many, f_pr_dir, f_db):
        assert len(list(self.p1.chroots)) == 15
        assert len(list(self.p1.copr.active_chroots)) == 15
        self.p1.chroot_blacklist_raw = '*'
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

        self.b1.source_status = StatusEnum("canceled")
        assert self.b1.finished

        self.b1.source_status = StatusEnum("failed")
        assert self.b1.finished
