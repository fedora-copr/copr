from unittest.mock import patch
from datetime import datetime, timedelta
from tests.coprs_test_case import CoprsTestCase
from coprs import app
from coprs.logic import coprs_logic
from coprs.mail import OutdatedChrootMessage
from commands.notify_outdated_chroots import get_user_chroots_map, filter_chroots, notify_outdated_chroots_function

def _get_user_chroots_sets(chroots, user):
    """ the list of CoprChroots is not ordered """
    with_hashes = get_user_chroots_map(chroots, user)
    with_sets = {}
    for key in with_hashes:
        with_sets[key] = set(with_hashes[key])
    return with_sets

class TestNotifyOutdatedChroots(CoprsTestCase):

    def test_user_chroots_map(self, f_users, f_coprs, f_mock_chroots, f_db):
        chroots = coprs_logic.CoprChrootsLogic.get_multiple().all()
        assert _get_user_chroots_sets(chroots, None) == {
            self.u1: set(self.c1.copr_chroots),
            self.u2: set(self.c2.copr_chroots + self.c3.copr_chroots),
        }

    def test_user_chroots_map_permissions(self, f_users, f_coprs, f_mock_chroots, f_copr_permissions, f_db):
        # With `f_copr_permissions`, `u1` is now one of the admis of `c3`
        chroots = coprs_logic.CoprChrootsLogic.get_multiple().all()
        assert _get_user_chroots_sets(chroots, None) == {
            self.u1: set(self.c1.copr_chroots + self.c3.copr_chroots),
            self.u2: set(self.c2.copr_chroots + self.c3.copr_chroots),
        }

    def test_user_chroots_map_email(self, f_users, f_coprs, f_mock_chroots, f_db):
        chroots = coprs_logic.CoprChrootsLogic.get_multiple().all()
        assert _get_user_chroots_sets(chroots, "user2@spam.foo") == \
            {self.u2: set(self.c2.copr_chroots + self.c3.copr_chroots)}


    def test_filter_chroots(self, f_users, f_coprs, f_mock_chroots, f_db):
        chroots = self.c1.copr_chroots + self.c2.copr_chroots

        # Do not care how recently was those chroots notified
        assert filter_chroots(chroots, all=True) == chroots

        # None of these chroots have been notified yet, hence we want to notify all
        assert filter_chroots(chroots, all=False) == chroots

        # We sent notification about this chroot yesterday, so don't spam about it
        chroots[0].delete_notify = datetime.today() - timedelta(days=1)
        assert filter_chroots(chroots, all=False) == chroots[1:]

        # The notification was sent ~3 monts ago, we want to send a new one
        chroots[0].delete_notify = datetime.today() - timedelta(days=90)
        assert filter_chroots(chroots, all=False) == chroots

    @patch("commands.notify_outdated_chroots.dev_instance_warning")
    @patch("commands.notify_outdated_chroots.send_mail")
    def test_notify_outdated_chroots(self, send_mail, dev_instance_warning, f_users, f_coprs, f_mock_chroots, f_db):
        app.config["SERVER_NAME"] = "localhost"
        with app.app_context():

            # Any copr chroots are marked to be deleted, hence there is nothing to be notified about
            notify_outdated_chroots_function(dry_run=False, email_filter=None, all=False)
            assert send_mail.call_count == 0

            # Mark a copr chroot to be deleted, we should send a notification
            self.c2.copr_chroots[0].mock_chroot.is_active = False
            self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=150)
            assert self.c2.copr_chroots[0].delete_notify is None
            notify_outdated_chroots_function(dry_run=False, email_filter=None, all=False)
            assert self.c2.copr_chroots[0].delete_notify is not None

            assert send_mail.call_count == 1
            recipients, message = send_mail.call_args[0]
            assert isinstance(message, OutdatedChrootMessage)
            assert recipients == ["user2@spam.foo"]
            assert "Project: user2/foocopr"
            assert "Chroot: fedora-17-x86_64"
            assert "Remaining: 149 days"

            # Run notifications immediately once more
            # Nothing should change, we have a mechanism to not spam users
            previous_delete_notify = self.c2.copr_chroots[0].delete_notify
            notify_outdated_chroots_function(dry_run=False, email_filter=None, all=False)
            assert send_mail.call_count == 1  # No new calls
            assert self.c2.copr_chroots[0].delete_notify == previous_delete_notify

            # Now, don't care when we sent last notifications. Notify everyone again
            notify_outdated_chroots_function(dry_run=False, email_filter=None, all=True)
            assert send_mail.call_count == 2
            assert self.c2.copr_chroots[0].delete_notify != previous_delete_notify

    @patch("commands.notify_outdated_chroots.dev_instance_warning")
    @patch("commands.notify_outdated_chroots.send_mail")
    def test_notify_outdated_chroots_email_filter(self, send_mail, dev_instance_warning,
                                                  f_users, f_coprs, f_mock_chroots, f_db):
        # Make sure that if `email_filter` is set, nobody else is going to be affected
        email_filter = ["somebody@nonexistent.ex"]
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=150)
        notify_outdated_chroots_function(dry_run=False, email_filter=email_filter, all=True)
        assert send_mail.call_count == 0
        assert not self.c2.copr_chroots[0].delete_notify
