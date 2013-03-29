import pytest

from coprs.exceptions import ActionInProgressException
from coprs.helpers import ActionTypeEnum, BackendResultEnum
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase

class TestCoprsLogic(CoprsTestCase):
    def test_update_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs, f_actions, f_db):
        self.c1.name = 'foo'
        with pytest.raises(ActionInProgressException):
            CoprsLogic.update(self.u1, self.c1)
        self.db.session.rollback()

    def test_legal_flag_doesnt_block_copr_functionality(self, f_users, f_coprs, f_db):
        self.db.session.add(self.models.Action(object_type='copr',
                                               object_id=self.c1.id,
                                               action_type=ActionTypeEnum('legal-flag')))
        self.db.session.commit()
        # test will fail if this raises exception
        CoprsLogic.raise_if_unfinished_blocking_action(None, self.c1, 'ha, failed')
