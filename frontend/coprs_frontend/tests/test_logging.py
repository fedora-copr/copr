# pylint: disable=cyclic-import
# pylint: disable=no-self-use

from unittest import TestCase
from unittest.mock import patch, MagicMock
import pytest
import flask
from munch import Munch
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator
from coprs import app, db, models, helpers
from coprs.views.misc import create_or_login, logout

from coprs.logic.users_logic import UsersLogic, UserDataDumper
from coprs.logic.coprs_logic import (
    CoprsLogic,
    CoprPermissionsLogic,
    CoprChrootsLogic,
)


class TestLoggingRequestUser(CoprsTestCase, TestCase):

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_server(self):
        with self.assertLogs(app.logger) as cm:
            app.logger.info("FOO")
            assert cm.records[0].user == "SERVER"

    @pytest.mark.usefixtures("f_u1_ts_client", "f_users", "f_coprs", "f_db")
    def test_user(self):
        with self.assertLogs(app.logger) as cm:
            self.api3.modify_project(self.c2.name, self.c2.owner_name)
            assert cm.records[0].user == "user1"

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_anon(self):
        with self.assertLogs(app.logger) as cm:
            self.tc.get("/coprs/user2", follow_redirects=True)
            assert cm.records[0].user == "ANON"


class TestLoggingUsersLogic(CoprsTestCase):

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_user_get(self, log):
        UsersLogic.get("somebody")
        log.info.assert_called_once_with(
            "Querying user '%s' by username", "somebody")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_raise_if_cant_update_copr(self, log):
        UsersLogic.raise_if_cant_update_copr(self.u2, self.c2, None)
        log.info.assert_called_once_with(
            "User '%s' allowed to update project '%s'",
            "user2", "user2/foocopr")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_raise_if_cant_build_in_copr(self, log):
        UsersLogic.raise_if_cant_build_in_copr(self.u2, self.c2, None)
        log.info.assert_called_once_with(
            "User '%s' allowed to build in project '%s'",
            "user2", "user2/foocopr")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_groups", "f_db")
    def test_raise_if_not_in_group(self, log):
        UsersLogic.raise_if_not_in_group(self.u1, self.g1)
        log.info.assert_called_once_with(
            "User '%s' allowed to access group '%s' (fas_name='%s')",
            "user1", "group1", "fas_1")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_delete_user_data(self, log):
        UsersLogic.delete_user_data(self.u2)
        log.info.assert_called_once_with("Deleting user '%s' data", "user2")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_create_user_wrapper(self, log):
        UsersLogic.create_user_wrapper("somebody", "somebody@example.test")
        log.info.assert_called_once_with("Creating user '%s <%s>'",
                                         "somebody", "somebody@example.test")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_user_data_dumper(self, log):
        dumper = UserDataDumper(self.u2)
        dumper.dumps()
        log.info.assert_called_once_with("Dumping all user data for '%s'",
                                         "user2")


class TestLoggingUserGeneral(CoprsTestCase):

    @patch("coprs.app.logger", return_value=MagicMock())
    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_delete_user_data(self, log):
        self.tc.get("/user/info/download")
        log.info.assert_called_once_with("Dumping all user data for '%s'",
                                         "user2")


class TestLoggingCoprPermissionsLogic(CoprsTestCase):

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_copr_permissions", "f_db")
    def test_update_permissions(self, log):
        perm = models.CoprPermission(
            copr=self.c2,
            user=self.u3,
            copr_builder=helpers.PermissionEnum("request"),
            copr_admin=helpers.PermissionEnum("request"))

        CoprPermissionsLogic.update_permissions(
            self.u2, self.c2, perm,
            new_builder=helpers.PermissionEnum("approved"),
            new_admin=helpers.PermissionEnum("nothing"))

        log.info.assert_called_with(
            "User '%s' authorized permission change for project '%s'"
            " - The '%s' user is now 'builder=%s', 'admin=%s'",
            "user2", "user2/foocopr", "user3", "approved", "nothing")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_copr_permissions", "f_db")
    def test_update_permissions_by_applier(self, log):
        CoprPermissionsLogic.update_permissions_by_applier(
            self.u2, self.c2, None,
            new_builder=helpers.PermissionEnum("request"),
            new_admin=helpers.PermissionEnum("nothing"))

        msg = ("User '%s' requests 'builder=%s', 'admin=%s' "
               "permissions for project '%s'")
        log.info.assert_called_once_with(
            msg, "user2", "request", "nothing", "user2/foocopr")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_copr_permissions", "f_db")
    def test_set_permissions(self, log):
        CoprPermissionsLogic.set_permissions(
            self.u2, self.c2, self.u3, "builder", "approved")
        log.info.assert_called_with(
            "User '%s' authorized permission change for project '%s'"
            " - The '%s' user is now '%s=%s'",
            "user2", "user2/foocopr", "user3", "builder", "approved")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_request_permission(self, log):
        CoprPermissionsLogic.request_permission(
            self.c1, self.u2, "builder", True)
        log.info.assert_called_once_with(
            "User '%s' requests '%s=%s' permission for project '%s'",
            "user2", "builder", "request", "user1/foocopr")


class TestLoggingAuth(CoprsTestCase):

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_create_or_login(self, log):
        resp = Munch({
            "identity_url": 'http://somebody.id.fedoraproject.org/',
            "email": "somebody@example.com",
            "timezone": "UTC",
            "extensions": {},
        })

        # Log in as user
        with app.test_request_context():
            create_or_login(resp)

        log.info.assert_any_call("Login for user '%s', creating "
                                 "a database record", "somebody")
        log.info.assert_called_with("%s '%s' logged in", "User", "somebody")

        # Modify user to be an admin
        user = models.User.query.filter_by(username="somebody").one()
        user.admin = True
        db.session.commit()

        # Log in as admin
        with app.test_request_context():
            create_or_login(resp)

        log.info.assert_called_with("%s '%s' logged in", "Admin", "somebody")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_db")
    def test_logout(self, log):
        with app.test_request_context():
            flask.g.user = self.u2
            logout()
        log.info.assert_called_with("User '%s' logging out", "user2")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_db")
    def test_api_login_required_invalid(self, log):
        headers = self.api3_auth_headers(self.u2)
        self.tc.post("/api_3/project/add/user2", headers=headers)

        log.info.assert_called_once_with(
            "Attempting to use invalid or expired API login '%s'", "abc")


class TestLoggingUsingAdminPermissions(CoprsTestCase):

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_update_copr(self, log):
        CoprsLogic.update(self.u1, self.c2)
        log.info.assert_called_with(
            "Admin '%s' using their permissions to update project '%s' settings",
            "user1", "user2/foocopr")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_update_copr_chroot(self, log):
        CoprChrootsLogic.update_chroot(self.u1, self.c2.copr_chroots[0])
        log.info.assert_called_with(
            "Admin '%s' using their permissions to update chroot '%s'",
            "user1", "user2/foocopr/fedora-17-x86_64")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_u1_ts_client", "f_coprs", "f_builds", "f_db")
    def test_update_package_webui(self, log):
        url = "/coprs/{0}/package/{1}/edit/scm".format(
            self.c2.full_name, self.p2.name)

        data = {
            "clone_url": "https://gitlab.com/zhanggyb/nerd-fonts.git",
            "package_name": self.p2.name,
        }

        self.tc.post(url, headers=self.auth_header, data=data)
        log.info.assert_called_with(
            "Admin '%s' using their permissions to update "
            "package '%s' in project '%s'",
            "user1", "whatsupthere-world", "user2/foocopr")

    @patch("coprs.app.logger", return_value=MagicMock())
    @pytest.mark.usefixtures("f_users", "f_u1_ts_client", "f_coprs", "f_builds", "f_db")
    def test_update_package_apiv3(self, log):
        url = "/api_3/package/edit/{0}/{1}/scm".format(
            self.c2.full_name, self.p2.name)

        data = {
            "clone_url": "https://gitlab.com/zhanggyb/nerd-fonts.git",
            "package_name": self.p2.name,
        }

        self.post_api3_with_auth(url, data, self.u1)
        log.info.assert_called_with(
            "Admin '%s' using their permissions to update "
            "package '%s' in project '%s'",
            "user1", "whatsupthere-world", "user2/foocopr")
