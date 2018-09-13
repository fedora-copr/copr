from coprs.mail import PermissionRequestMessage, PermissionChangeMessage, LegalFlagMessage
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
