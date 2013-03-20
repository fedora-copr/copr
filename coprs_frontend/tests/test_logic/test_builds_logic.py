from coprs.logic.builds_logic import BuildsLogic
from tests.coprs_test_case import CoprsTestCase

class TestBuildsLogic(CoprsTestCase):
    def test_add_only_adds_active_chroots(self, f_users, f_coprs, f_builds, f_mock_chroots, f_db):
        self.mc2.is_active = False
        self.db.session.commit()
        b = BuildsLogic.add(self.u2, 'blah blah', self.c2)
        self.db.session.commit()
        assert b.chroots == self.mc3.chroot_name
