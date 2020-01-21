from datetime import datetime, timedelta
from tests.coprs_test_case import CoprsTestCase
from coprs.logic.actions_logic import ActionsLogic
from copr_common.enums import ActionTypeEnum
from commands.delete_outdated_chroots import delete_outdated_chroots_function

class TestDeleteOutdatedChroots(CoprsTestCase):

    def test_delete_outdated(self, f_users, f_coprs, f_mock_chroots, f_db):
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 0

    def test_delete_outdated_yesterday(self, f_users, f_coprs, f_mock_chroots, f_db):
        # This chroot expired yesterday and should be removed
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 1
        assert self.c2.copr_chroots[0].delete_after is None

    def test_delete_outdated_not_yet(self, f_users, f_coprs, f_mock_chroots, f_db):
        # This chroot will expire tomorrow, so don't remove it yet
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=1)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 0
        assert self.c2.copr_chroots[0].delete_after is not None
