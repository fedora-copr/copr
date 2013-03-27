import pytest

from coprs.exceptions import ActionInProgressException
from coprs.helpers import BackendResultEnum
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase

class TestCoprsLogic(CoprsTestCase):
    def test_update_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs, f_actions, f_db):
        self.c1.name = 'foo'
        with pytest.raises(ActionInProgressException):
            CoprsLogic.update(self.u1, self.c1)
        self.db.session.rollback()
