from unittest.mock import patch
from datetime import datetime, timedelta
import pytest
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
        self.c2.copr_chroots[0].mock_chroot.is_active = False
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        self.c2.copr_chroots[0].delete_notify = datetime.fromtimestamp(123)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 1
        assert self.c2.copr_chroots[0].delete_after is None

    def test_delete_outdated_not_yet(self, f_users, f_coprs, f_mock_chroots, f_db):
        # This chroot will expire tomorrow, so don't remove it yet
        self.c2.copr_chroots[0].mock_chroot.is_active = False
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=1)
        self.c2.copr_chroots[0].delete_notify = datetime.fromtimestamp(123)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 0
        assert self.c2.copr_chroots[0].delete_after is not None

    @patch("commands.delete_outdated_chroots.app.logger.error")
    def test_delete_outdated_handle_none_notify(self, logerror, f_users, f_coprs, f_mock_chroots, f_db):
        self.c2.copr_chroots[0].mock_chroot.is_active = False
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        delete_outdated_chroots_function(dry_run=False)

        assert logerror.call_count == 1
        msg, full_name, chroot = logerror.call_args[0]
        assert "Refusing to delete" in msg
        assert full_name == "user2/foocopr"
        assert chroot == "fedora-17-x86_64"

        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 0
        assert self.c2.copr_chroots[0].delete_after is not None

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_delete_unclicked(self):
        """
        Test that we know how to delete backend data from chroots that user
        manually unclicked from a project
        """

        # Chroots unclicked by user cannot be inactive or EOL and we don't want
        # to send any email notifications about them
        assert self.c2.copr_chroots[0].mock_chroot.is_active
        assert not self.c2.copr_chroots[0].delete_notify

        # This chroot was unclicked from a project and its data is supposed to
        # be deleted tomorrow
        self.c2.copr_chroots[0].deleted = True
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=1)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 0

        # Going into the future, let's say the data expired yesterday
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        delete_outdated_chroots_function(dry_run=False)
        actions = ActionsLogic.get_many(ActionTypeEnum("delete")).all()
        assert len(actions) == 1

        # Make sure once again that we didn't try to notify about such chroot
        assert not self.c2.copr_chroots[0].delete_notify
