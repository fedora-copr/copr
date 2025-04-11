import pytest
import datetime
from coprs.mail import PermissionRequestMessage, PermissionChangeMessage, LegalFlagMessage, OutdatedChrootMessage, filter_allowlisted_recipients
from coprs import app, models
from tests.coprs_test_case import CoprsTestCase


class TestMail(CoprsTestCase):
    def test_permissions_request_message(self, f_users, f_coprs, f_copr_permissions, f_db):
        msg = PermissionRequestMessage(self.c1, self.u2, {"new_builder": 1, "new_admin": 0})
        assert msg.subject == "[Copr] user1/foocopr: user2 is requesting permissions change"
        assert msg.text == ("user2 asked for these changes:\n\n"
                            "Builder: nothing -> request\n"
                            "Admin: nothing -> nothing\n\n"
                            "Project: user1/foocopr")

        msg = PermissionRequestMessage(self.c1, self.u2, {"old_admin": 1, "new_admin": 0})
        assert msg.subject == "[Copr] user1/foocopr: user2 is requesting permissions change"
        assert msg.text == ("user2 asked for these changes:\n\n"
                            "Admin: request -> nothing\n\n"
                            "Project: user1/foocopr")

    def test_permissions_change_message(self, f_users, f_coprs, f_copr_permissions, f_db):
        msg = PermissionChangeMessage(self.c1, {"old_builder": 0, "old_admin": 2, "new_builder": 2, "new_admin": 0})
        assert msg.subject == "[Copr] user1/foocopr: Your permissions have changed"
        assert msg.text == ("Your permissions have changed:\n\n"
                            "Builder: nothing -> approved\n"
                            "Admin: approved -> nothing\n\n"
                            "Project: user1/foocopr")

        msg = PermissionChangeMessage(self.c1, {"old_builder": 0, "new_builder": 1})
        assert msg.subject == "[Copr] user1/foocopr: Your permissions have changed"
        assert msg.text == ("Your permissions have changed:\n\n"
                            "Builder: nothing -> request\n\n"
                            "Project: user1/foocopr")

        msg = PermissionChangeMessage(self.c1, {"old_admin": 1, "new_admin": 0})
        assert msg.subject == "[Copr] user1/foocopr: Your permissions have changed"
        assert msg.text == ("Your permissions have changed:\n\n"
                            "Admin: request -> nothing\n\n"
                            "Project: user1/foocopr")

    def test_legal_flag_message(self, f_users, f_coprs, f_db):
        app.config["SERVER_NAME"] = "localhost"
        with app.app_context():
            msg = LegalFlagMessage(self.c1, self.u2, "There are forbidden packages in the project")
            assert msg.subject == "Legal flag raised on foocopr"
            assert msg.text == ("There are forbidden packages in the project\n"
                                "Navigate to http://localhost/admin/legal-flag/\n"
                                "Contact on owner is: user1 <user1@foo.bar>\n"
                                "Reported by user2 <user2@spam.foo>")

    def test_outdated_chroot_message(self, f_users, f_coprs, f_mock_chroots, f_db):
        chroots = self.c1.copr_chroots + self.c2.copr_chroots + self.c3.copr_chroots

        # Create more chroots within one project to later make sure line
        # wrapping works as expected
        for i in range(30, 38):
            mc = models.MockChroot(os_release="fedora", os_version=i,
                                   arch="x86_64", is_active=True)
            mc.distgit_branch = models.DistGitBranch.query.first()
            self.db.session.add(mc)

            cc = models.CoprChroot()
            cc.mock_chroot = mc
            cc.copr = self.c2
            self.db.session.add(cc)
            chroots.append(cc)

        now = datetime.datetime.now()
        for chroot in chroots:
            # 7 days = 6d, 23h, 59m, ...
            if chroot.copr.full_name == "user2/barcopr" \
                    and chroot.name == "fedora-18-x86_64":
                # special-case one chroot to make a message variation
                chroot.delete_after = now + datetime.timedelta(days=5 + 1)
            else:
                chroot.delete_after = now + datetime.timedelta(days=7 + 1)

        app.config["SERVER_NAME"] = "localhost"
        app.config["DELETE_EOL_CHROOTS_AFTER"] = 123
        with app.app_context():
            msg = OutdatedChrootMessage(chroots)
        assert msg.subject == "[Copr] upcoming deletion of outdated chroots in your projects"
        assert msg.text == ("You have been notified because you are an admin of projects, "
                            "that have some builds in outdated chroots\n\n"

                            "According to the 'Copr outdated chroots removal policy'\n"
                            "https://docs.pagure.org/copr.copr/copr_outdated_chroots_removal_policy.html\n"
                            "data are going to be preserved 123 days after the chroot is EOL "
                            "and then automatically deleted, unless you decide to prolong the expiration period.\n\n"

                            "Please, visit the projects settings if you want to extend the time.\n\n"

                            "Project: user1/foocopr\n"
                            "Remaining time:\n"
                            "  7 days:\n"
                            "    fedora-18-x86_64\n"
                            "https://localhost/coprs/user1/foocopr/repositories/\n\n"

                            "Project: user2/foocopr\n"
                            "Remaining time:\n"
                            "  7 days:\n"
                            "    fedora-17-i386 fedora-17-x86_64 fedora-30-x86_64 fedora-31-x86_64\n"
                            "    fedora-32-x86_64 fedora-33-x86_64 fedora-34-x86_64 fedora-35-x86_64\n"
                            "    fedora-36-x86_64 fedora-37-x86_64\n"
                            "https://localhost/coprs/user2/foocopr/repositories/\n\n"

                            "Project: user2/barcopr\n"
                            "Remaining time:\n"
                            "  5 days:\n"
                            "    fedora-18-x86_64\n"
                            "  7 days:\n"
                            "    fedora-rawhide-i386\n"
                            "https://localhost/coprs/user2/barcopr/repositories/\n\n")

    def test_outdated_chroot_message_empty_chroots(self):
        with pytest.raises(AttributeError) as ex:
            OutdatedChrootMessage(copr_chroots=[])
        assert "No outdated chroots" in str(ex)

    def test_filter_recipients(self):
        app.config["ALLOWLIST_EMAILS"] = ["test@redhat.com"]
        recipient = filter_allowlisted_recipients(["test@redhat.com", "user@redhat.com"])
        assert recipient == ["test@redhat.com"]

        app.config["ALLOWLIST_EMAILS"] = ["test@redhat.com", "user@redhat.com"]
        recipient = filter_allowlisted_recipients(["test@redhat.com", "user@redhat.com"])
        assert recipient == ["test@redhat.com", "user@redhat.com"]

        app.config["ALLOWLIST_EMAILS"] = []
        recipient = filter_allowlisted_recipients(["test@redhat.com", "user@redhat.com"])
        assert recipient == ["test@redhat.com", "user@redhat.com"]
