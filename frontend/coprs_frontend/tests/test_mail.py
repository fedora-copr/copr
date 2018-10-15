import datetime
from coprs.mail import PermissionRequestMessage, PermissionChangeMessage, LegalFlagMessage, OutdatedChrootMessage
from tests.coprs_test_case import CoprsTestCase
from coprs import app


class TestMail(CoprsTestCase):
    def test_permissions_request_message(self, f_users, f_coprs, f_copr_permissions, f_db):
        msg = PermissionRequestMessage(self.c1, self.u2, {"new_builder": 1, "new_admin": 0})
        assert msg.subject == "[Copr] foocopr: user2 is asking permissions"
        assert msg.text == ("user2 is asking for these permissions:\n\n"
                            "Builder: nothing -> request\n"
                            "Admin: nothing -> nothing\n\n"
                            "Project: foocopr\n"
                            "Owner: user1")

    def test_permissions_change_message(self, f_users, f_coprs, f_copr_permissions, f_db):
        msg = PermissionChangeMessage(self.c1, {"old_builder": 0, "old_admin": 2, "new_builder": 2, "new_admin": 0})
        assert msg.subject == "[Copr] foocopr: Your permissions have changed"
        assert msg.text == ("Your permissions have changed:\n\n"
                            "Builder: nothing -> approved\n"
                            "Admin: approved -> nothing\n\n"
                            "Project: foocopr\n"
                            "Owner: user1")

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
        for chroot in self.c2.copr_chroots:
            chroot.delete_after = datetime.datetime.now() + datetime.timedelta(days=7 + 1) # 7 days = 6d, 23h, 59m, ...

        app.config["SERVER_NAME"] = "localhost"
        with app.app_context():
            msg = OutdatedChrootMessage(self.c2, self.c2.copr_chroots)
        assert msg.subject == "Upcoming deletion of outdated chroots in foocopr"
        assert msg.text == ("You have been notified, as a project user2/foocopr admin, that it has some builds in "
                            "outdated chroot(s).\n\n"
                            "According to the 'Copr outdated chroots removal policy' [1], data are going"
                            "to be preserved 180 days after the chroot is EOL and then automatically deleted,"
                            "unless you decide to prolong the expiration period.\n\n"

                            "Project: user2/foocopr\n"
                            "Chroot: fedora-17-x86_64\n"
                            "Remaining: 7 days\n\n"

                            "Project: user2/foocopr\n"
                            "Chroot: fedora-17-i386\n"
                            "Remaining: 7 days\n\n"

                            "Please, visit the project settings [2] if you want to extend the time.\n\n"
                            "[1] https://docs.pagure.org/copr.copr/copr_outdated_chroots_removal_policy.html"
                            "[2] http://localhost/coprs/user2/foocopr/repositories/")
