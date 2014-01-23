import pytest

from coprs.exceptions import ActionInProgressException
from coprs.logic.builds_logic import BuildsLogic

from tests.coprs_test_case import CoprsTestCase

class TestBuildsLogic(CoprsTestCase):
    def test_add_only_adds_active_chroots(self, f_users, f_coprs, f_builds, f_mock_chroots, f_db):
        self.mc2.is_active = False
        self.db.session.commit()
        b = BuildsLogic.add(self.u2, 'blah blah', self.c2)
        self.db.session.commit()
        assert b.chroots[0].name == self.mc3.name

    def test_add_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs, f_actions, f_db):
        with pytest.raises(ActionInProgressException):
            b = BuildsLogic.add(self.u1, 'blah blah', self.c1)
        self.db.session.rollback()

    def test_add_assigns_params_correctly(self, f_users, f_coprs, f_mock_chroots, f_db):
        params = dict(
            user=self.u1,
            pkgs='blah blah',
            copr=self.c1,
            repos='repos',
            memory_reqs=3000,
            timeout=5000)

        b = BuildsLogic.add(**params)
        for k, v in params.items():
            assert getattr(b, k) == v
