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
