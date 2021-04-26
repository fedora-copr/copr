from datetime import datetime, timedelta
from unittest.mock import patch
import flask
import pytest
from copr_common.enums import ActionTypeEnum
from tests.coprs_test_case import CoprsTestCase, new_app_context
from coprs.logic.outdated_chroots_logic import OutdatedChrootsLogic
from coprs.logic.coprs_logic import CoprChrootsLogic
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import ChrootDeletionStatus
from coprs import app
from commands.alter_chroot import func_alter_chroot
from commands.delete_outdated_chroots import delete_outdated_chroots_function
from commands.notify_outdated_chroots import notify_outdated_chroots_function


class TestOutdatedChrootsLogic(CoprsTestCase):

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_delete_status_outdated(self):
        """
        Transition within all steps of all chroot EOL process and make sure
        the `delete_status` returns expected states
        """
        chroot = self.c2.copr_chroots[0]

        # Normal, active chroot
        assert chroot.is_active
        assert not chroot.delete_after
        assert not chroot.delete_notify
        assert chroot.delete_status == ChrootDeletionStatus("active")

        # Chroot is deactivated
        chroot.mock_chroot.is_active = False
        assert chroot.delete_status == ChrootDeletionStatus("deactivated")
        assert chroot.delete_status_str == "deactivated"

        # Chroot is EOLed
        chroot.delete_after = datetime.now() + timedelta(days=180)
        assert chroot.delete_status == ChrootDeletionStatus("preserved")
        assert chroot.delete_status_str == "preserved"

        # Within next cronjob, we sent emails
        chroot.delete_notify = datetime.now()
        assert chroot.delete_status == ChrootDeletionStatus("preserved")
        assert chroot.delete_status_str == "preserved"

        # After the preservation period is gone
        chroot.delete_after = datetime.now() - timedelta(days=1)
        assert chroot.delete_status == ChrootDeletionStatus("expired")
        assert chroot.delete_status_str == "expired"

        # Within next cronjob, we deleted the data
        chroot.delete_after = None
        assert chroot.delete_status == ChrootDeletionStatus("deleted")
        assert chroot.delete_status_str == "deleted"

        # Special case - we wasn't able to send any notification emails,
        # therefore the chroot is preserved even after the standard
        # preservation period is gone
        chroot.delete_after = datetime.now() - timedelta(days=1)
        chroot.delete_notify = None
        assert chroot.delete_status == ChrootDeletionStatus("preserved")
        assert chroot.delete_status_str == "preserved"

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_delete_status_unclicked(self):
        """
        Transition within all steps that unclicked chroot goes through and make
        sure the `delete_status` returns expected states
        """
        chroot = self.c2.copr_chroots[0]

        # Normal, active chroot
        assert not chroot.deleted
        assert chroot.delete_status == ChrootDeletionStatus("active")

        # User un-clicks the chroot from project settings
        chroot.deleted = True
        chroot.delete_after = datetime.now() + timedelta(days=7)
        assert chroot.delete_status == ChrootDeletionStatus("preserved")

        # After the preservation period is gone
        chroot.delete_after = datetime.now() - timedelta(days=1)
        assert chroot.delete_status == ChrootDeletionStatus("expired")

        # Within next cronjob, we deleted the data
        chroot.delete_after = None
        assert chroot.delete_status == ChrootDeletionStatus("deleted")

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_simple(self):
        # Make sure, that there are no unreviewed outdated chroots yet
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u2)

        # Once a chroot is EOLed, we should see that a user has something unreviewed
        self.c2.copr_chroots[0].mock_chroot.is_active = False
        self.c2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=10)
        assert OutdatedChrootsLogic.has_not_reviewed(self.u2)

        # User just reviewed his outdated chroots
        # (e.g. by visiting the /repositories page)
        OutdatedChrootsLogic.make_review(self.u2)
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u2)

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_groups", "f_group_copr", "f_db")
    def test_outdated_chroots_group(self):
        # Make sure that a user is a part of a group
        self.u3.openid_groups = {"fas_groups": [self.g1.fas_name]}
        assert self.u3.can_build_in_group(self.g1)

        # Make sure a project is owned by a group but not by our user himself
        permissible = ComplexLogic.get_coprs_permissible_by_user(self.u3)
        assert self.gc2 in permissible
        assert self.gc2.user != self.u3

        # Make sure, that there are no unreviewed outdated chroots yet
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u3)

        # Once a chroot is EOLed, we should see that a user has something unreviewed
        self.gc2.copr_chroots[0].mock_chroot.is_active = False
        self.gc2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=10)
        assert OutdatedChrootsLogic.has_not_reviewed(self.u3)

        # User just reviewed his outdated chroots
        # (e.g. by visiting the /repositories page)
        OutdatedChrootsLogic.make_review(self.u3)
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u3)

        # Only a `self.u3` did the review, other group members still has
        # unreviewed chroots
        self.u2.openid_groups = {"fas_groups": [self.g1.fas_name]}
        assert OutdatedChrootsLogic.has_not_reviewed(self.u2)

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_flash_not_immediately(self):
        # Make sure, that there are no unreviewed outdated chroots yet
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u2)

        # A chroot was just marked as EOL, we don't want to see any warning just yet
        self.c2.copr_chroots[0].mock_chroot.is_active = False
        self.c2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=180)
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u2)

        # Once around half of the preservation period for an EOLed chroot
        # runned out, we want to start showing some notification
        self.c2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=80)
        assert OutdatedChrootsLogic.has_not_reviewed(self.u2)

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_flash_not_expired(self):
        # A preservation period is gone and the chroot is scheduled to be
        # deleted ASAP. At this point, user has no chance to extend it anymore,
        # so make sure we don't notify him about such chroots
        self.c2.copr_chroots[0].delete_after = datetime.now() - timedelta(days=1)
        assert not OutdatedChrootsLogic.has_not_reviewed(self.u2)

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_review_only_after_some_time(self):
        # Make sure that `self.u2` hasn't reviewed anything yet
        assert not OutdatedChrootsLogic.get_all_reviews(self.u2).all()

        # Some chroots are going to be deleted, with various times remaining
        self.c2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=35)
        self.c2.copr_chroots[1].delete_after = datetime.now() + timedelta(days=160)
        self.c3.copr_chroots[0].delete_after = datetime.now() + timedelta(days=80)
        self.c3.copr_chroots[1].delete_after = datetime.now() + timedelta(days=50)

        # User just reviewed his outdated chroots
        # (e.g. by visiting the /repositories page)
        OutdatedChrootsLogic.make_review(self.u2)
        reviews = OutdatedChrootsLogic.get_all_reviews(self.u2).all()

        # Make sure that not all EOL chroots have been reviewed. We want to
        # review only those with a significant portion of the preservation
        # period already run out.
        assert len(reviews) == 3
        assert self.c2.copr_chroots[1] not in [x.copr_chroot for x in reviews]
        assert {x.copr_chroot for x in reviews} == {
            self.c2.copr_chroots[0],
            self.c3.copr_chroots[0],
            self.c3.copr_chroots[1],
        }

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_extend_or_expire(self):
        # Make sure that `self.u2` hasn't reviewed anything yet
        assert len(OutdatedChrootsLogic.get_all_reviews(self.u2).all()) == 0

        # Let's have some outdated chroot
        self.c2.copr_chroots[0].delete_after = datetime.now() + timedelta(days=35)

        # Make sure a user reviewed it
        OutdatedChrootsLogic.make_review(self.u2)
        assert len(OutdatedChrootsLogic.get_all_reviews(self.u2).all()) == 1

        # Extend should properly extend the preservation period
        # and drop the review
        flask.g.user = self.u2
        OutdatedChrootsLogic.extend(self.c2.copr_chroots[0])
        assert (self.c2.copr_chroots[0].delete_after
                > datetime.now() + timedelta(days=35))
        assert len(OutdatedChrootsLogic.get_all_reviews(self.u2).all()) == 0

        # User changed his mind and expired the chroot instead
        OutdatedChrootsLogic.expire(self.c2.copr_chroots[0])
        expected = (datetime.now() +
                    timedelta(days=app.config["EOL_CHROOTS_EXPIRE_PERIOD"]))
        assert (self.c2.copr_chroots[0].delete_after.date()
                == expected.date())

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_humanized(self):
        chroot = self.c2.copr_chroots[0]
        chroot.mock_chroot.is_active = False
        chroot.delete_after = datetime.now() + timedelta(days=35)
        assert chroot.delete_after_humanized == "34 days"

        chroot.delete_after = datetime.now() + timedelta(days=2)
        assert chroot.delete_after_humanized == "1 days"

        chroot.delete_after = datetime.now() + timedelta(hours=12)
        assert chroot.delete_after_humanized == "12 hours"

        chroot.delete_after = datetime.now() + timedelta(minutes=30)
        assert chroot.delete_after_humanized == "less then an hour"

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_chroots_expired(self):
        chroot = self.c2.copr_chroots[0]
        chroot.mock_chroot.is_active = False
        chroot.delete_notify = datetime.now()

        chroot.delete_after = datetime.now() + timedelta(days=35)
        assert not chroot.delete_after_expired

        chroot.delete_after = datetime.now() + timedelta(days=-35)
        assert chroot.delete_after_expired

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_expired_chroot_detection(self):
        """
        Test fix for issue #1682, that expired chroots are not printed out.
        """

        def _assert_unaffected(cc):
            assert cc.is_active is True
            assert cc.delete_after is None
            assert cc.delete_notify is None

        # (1) Somewhere in the future (now +180 days by default) fedora-17 is
        #     going to be expired.
        func_alter_chroot(["fedora-17-x86_64", "fedora-17-i386"], "eol")
        found = 0
        for cc in self.models.CoprChroot.query.all():
            if "fedora-17" in cc.name:
                assert cc.delete_after >= datetime.now() + timedelta(days=179)
                assert cc.delete_notify is None
                assert cc.delete_after_expired is False
                # simulate that some mails were sent
                cc.delete_notify = datetime.now()
                continue
            _assert_unaffected(cc)

        # (2) Reactivate the chroots.  Happened at least for epel-7 chroots
        #     historically.
        func_alter_chroot(["fedora-17-x86_64", "fedora-17-i386"], "activate")
        for cc in self.models.CoprChroot.query.all():
            assert cc.delete_after_expired is False
            _assert_unaffected(cc)

        # (3) Mark as EOL again, when is appropriate time.  And Expire.
        backup = self.app.config["DELETE_EOL_CHROOTS_AFTER"]
        self.app.config["DELETE_EOL_CHROOTS_AFTER"] = 0
        func_alter_chroot(["fedora-17-x86_64", "fedora-17-i386"], "eol")
        self.app.config["DELETE_EOL_CHROOTS_AFTER"] = backup
        found = 0
        for cc in self.models.CoprChroot.query.all():
            if "fedora-17" in cc.name:
                found += 1
                assert cc.is_active is False
                assert cc.delete_after <= datetime.now() + timedelta(days=179)
                assert cc.delete_notify is None
                # Because we didn't send any notification, the chroot is not
                # considered to be expired even though the standard
                # preservation time is gone
                assert cc.delete_after_expired is False
                # unblock the delete action
                cc.delete_notify = datetime.now()
            else:
                _assert_unaffected(cc)
        assert found == 2

        # (4) Delete the expired chroots!
        delete_outdated_chroots_function(False)
        found = 0
        for cc in self.models.CoprChroot.query.all():
            if "fedora-17" in cc.name:
                found += 1
                assert cc.is_active is False
                assert cc.delete_after is None
                assert cc.delete_notify is not None
                assert cc.delete_after_expired is True
            else:
                _assert_unaffected(cc)
        assert found == 2

    @patch("commands.notify_outdated_chroots.dev_instance_warning")
    @patch("commands.notify_outdated_chroots.send_mail")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_delete_outdated_unclicked(self, send_mail, _dev_instance_warning):
        """
        A corner case that probably won't happen very often.
        Let's say that user has some chroot (F17) enabled and because it is
        reaching EOL, he decides to not care about it anymore and disable it.
        This means the chroot data will be preserved for only a couple of days
        and no email notification is going to be sent.

        Within this short preservation period we indeed mark the chroot as EOL,
        which would normally mean 180 days preservation period and email
        notifications but since the chroot was manually unclicked by the project
        owner, we don't want any of those.

        This test makes sure that marking a chroot as EOL doesn't affect such
        chroots that were already been unclicked from a project.
        """
        assert len(self.c2.copr_chroots) == 2
        assert self.c2.copr_chroots[0].name == "fedora-17-x86_64"

        # User unclicks a chroot from his project. The chroot data should be
        # deleted within a couple of days
        CoprChrootsLogic.remove_copr_chroot(self.u2, self.c2.copr_chroots[0])
        delete_after = self.c2.copr_chroots[0].delete_after
        assert delete_after

        # Meanwhile we marked the chroot as EOL
        func_alter_chroot(["fedora-17-x86_64"], "eol")

        # Make sure the EOL process didn't interfere and the data is still
        # going to be deleted within a couple of days
        assert self.c2.copr_chroots[0].delete_after == delete_after

        # Also make sure we will not send email notifications about the chroot
        notify_outdated_chroots_function(
            dry_run=False, email_filter=None, all=True)
        assert send_mail.call_count == 0

        # Test that the data deletion is not blocked by missing notification
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=7)
        assert len(ActionsLogic.get_many(ActionTypeEnum("delete")).all()) == 0
        delete_outdated_chroots_function(dry_run=False)
        assert len(ActionsLogic.get_many(ActionTypeEnum("delete")).all()) == 1


    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_outdated_unclicked_repeat(self):
        """
        A corner case when user decides to unclick a chroot from his project
        and in the meantime, Copr administrators repeatedly disable, EOL and
        activate it. The copr_chroot instance shouldn't be affected by this at
        all. Then user can enable it again.
        """
        # User unclicks a chroot from his project. The chroot data should be
        CoprChrootsLogic.remove_copr_chroot(self.u2, self.c2.copr_chroots[0])
        delete_after = self.c2.copr_chroots[0].delete_after
        assert delete_after

        # Meanwhile, Copr administrators decide to EOL, and reactivate the
        # mock_chroot several times. The copr_chrot isn't affected.
        for action in 2 * ["deactivate", "eol", "activate"]:
            func_alter_chroot(["fedora-17-x86_64"], action)
        assert self.c2.copr_chroots[0].delete_after == delete_after

        # User decide to enable the chroot in his project again
        CoprChrootsLogic.update_from_names(
            self.u2, self.c2, [chroot.name for chroot in self.c2.copr_chroots])
        assert not self.c2.copr_chroots[0].delete_after
