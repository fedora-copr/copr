import json
from unittest.mock import patch, MagicMock

from coprs.models import User, Copr

from tests.coprs_test_case import CoprsTestCase

from coprs.views.apiv3_ns import apiv3_projects


class TestApiV3Permissions(CoprsTestCase):

    def auth_get(self, path, user):
        base = "/api_3/project/permissions"
        return self.get_api3_with_auth(base + path, user)

    def auth_post(self, path, data, user):
        base = "/api_3/project/permissions"
        return self.post_api3_with_auth(base + path, data, user)

    def test_perms_get_require_admin(self, f_users, f_coprs, f_mock_chroots,
                                     f_copr_more_permissions, f_users_api, f_db):

        r = self.tc.get("/api_3/project/permissions/get/user2/foocopr")
        assert r.status_code == 401

        # user3 is "nothing:nothing" on c3
        u = User.query.filter_by(username='user3').first()
        r = self.auth_get("/get/user2/barcopr", u)
        assert r.status_code == 403

        # user4 is only a builder in c1
        u = User.query.filter_by(username='user4').first()
        r = self.auth_get("/get/user2/barcopr", u)
        assert r.status_code == 403

    def test_no_permission_set(self, f_users, f_coprs, f_mock_chroots,
                               f_copr_permissions, f_users_api, f_db):
        # u1 is authorized, but no permission is set on c1 copr
        u1 = User.query.filter_by(username='user1').first()
        r = self.get_api3_with_auth(
            "/api_3/project/permissions/get/user1/foocopr",
            u1)
        assert r.status_code == 404
        assert 'No permissions set on' in json.loads(r.data)['error']

    def test_perms_accessible_by_user(self, f_users, f_coprs, f_mock_chroots,
                                      f_copr_permissions, f_users_api, f_db):
        # test owner
        exp_data = {'permissions': {'user1': {'admin': 'nothing', 'builder': 'approved'}}}
        u = User.query.filter_by(username='user2').first()
        r = self.get_api3_with_auth(
            "/api_3/project/permissions/get/user2/foocopr", u)
        assert r.status_code == 200
        assert json.loads(r.data) == exp_data

        u = User.query.filter_by(username='user1').first()
        r = self.get_api3_with_auth(
            "/api_3/project/permissions/get/user2/foocopr", u)
        assert r.status_code == 200
        assert json.loads(r.data) == exp_data

    def test_perms_set_require_admin(self, f_users, f_coprs, f_mock_chroots,
                                     f_copr_more_permissions, f_users_api, f_db):

        r = self.tc.post("/api_3/project/permissions/set/some/non-existent",
                         data="something")
        assert r.status_code == 401

        # even authorized non-admin user isn't able to set the permissions
        u3 = User.query.filter_by(username='user3').first()
        r = self.post_api3_with_auth(
            "/api_3/project/permissions/set/user2/foocopr", {}, u3)
        assert r.status_code == 403

        # even authorized non-admin user isn't able to set the permissions
        u = User.query.filter_by(username='user4').first()
        r = self.auth_post("/set/user2/barcopr", {}, u)
        assert r.status_code == 403

    def test_set_bad_data(self, f_users, f_coprs, f_mock_chroots,
                          f_copr_permissions, f_users_api, f_db):
        # test owner
        u = User.query.filter_by(username='user2').first()
        r = self.auth_post("/set/user2/barcopr", {}, u)
        assert r.status_code == 400

        r = self.auth_post("/set/user2/barcopr", {'non_existent': {'admin': 'approved'}}, u)
        assert r.status_code == 400

        r = self.auth_post("/set/user2/barcopr", {'user2': {'admin': 'approved'}}, u)
        assert r.status_code == 400
        print(r.data)

    def test_settable(self, f_users, f_coprs, f_mock_chroots,
                      f_copr_more_permissions, f_users_api, f_db):
        # by owner
        exp_data = {'permissions': {'user1': {'admin': 'nothing', 'builder': 'approved'}}}
        u = User.query.filter_by(username='user2').first()
        perms = {'user4': {'admin': 'approved'}}
        r = self.auth_post("/set/user2/foocopr", perms, u)
        assert r.status_code == 200
        assert json.loads(r.data) == {'updated': ['user4']}

        # by owner repeated
        u = User.query.filter_by(username='user2').first()
        r = self.auth_post("/set/user2/foocopr", perms, u)
        assert r.status_code == 200
        assert json.loads(r.data) == {'updated': []}

        # test admin
        u = User.query.filter_by(username='user1').first()
        perms = {'user3': {'builder': 'approved'}}
        r = self.auth_post("/set/user2/barcopr", perms, u)
        assert r.status_code == 200
        assert json.loads(r.data) == {'updated': ['user3']}

    def test_cant_readd_owner(self, f_users, f_coprs, f_mock_chroots,
                              f_copr_more_permissions, f_users_api, f_db):
        u = User.query.filter_by(username='user1').first()
        perms = {'user2': {'builder': 'approved'}}
        r = self.auth_post("/set/user2/barcopr", perms, u)
        assert r.status_code == 400
        assert 'is owner of the' in json.loads(r.data)['error']

    def test_request_invalid(self, f_users, f_coprs, f_mock_chroots,
                             f_copr_more_permissions, f_users_api, f_db):
        r = self.tc.get("/api_3/project/permissions/request/user2/foocopr")
        assert r.status_code == 405
        r = self.tc.post("/api_3/project/permissions/request/user2/foocopr",
                         content_type="application/json",
                         data={})
        assert r.status_code == 401

        u = User.query.filter_by(username='user1').first()
        invalid_request = {'admin': 1}
        r = self.auth_post("/request/user2/foocopr", invalid_request, u)
        assert r.status_code == 400
        assert "invalid 'admin' permission request" in json.loads(r.data)['error']

        u = User.query.filter_by(username='user1').first()
        invalid_request = {'admin_invalid': True}
        r = self.auth_post("/request/user2/foocopr", invalid_request, u)
        assert r.status_code == 400
        assert "invalid permission 'admin_invalid'" in json.loads(r.data)['error']

        # u1 is already admin
        u = User.query.filter_by(username='user1').first()
        r = self.auth_post("/request/user2/barcopr", {}, u)
        assert r.status_code == 400
        assert 'no permission' in json.loads(r.data)['error']

        # u2 is owner
        u = User.query.filter_by(username='user2').first()
        r = self.auth_post("/request/user2/barcopr", {'admin': False}, u)
        assert r.status_code == 400
        assert 'is owner' in json.loads(r.data)['error']

    def test_request_valid(self, f_users, f_coprs, f_mock_chroots,
                           f_copr_more_permissions, f_users_api, f_db):
        u = User.query.filter_by(username='user4').first()
        permissions = {'admin': True}
        r = self.auth_post("/request/user2/barcopr", permissions, u)
        assert r.status_code == 200
        assert json.loads(r.data)['updated'] == True

        # re-request, but no update
        u = User.query.filter_by(username='user4').first()
        r = self.auth_post("/request/user2/barcopr", permissions, u)
        assert r.status_code == 200
        assert json.loads(r.data)['updated'] == False

    @patch('coprs.views.apiv3_ns.apiv3_permissions.send_mail',
           new_callable=MagicMock())
    def test_perms_set_sends_emails(
            self, send_mail, f_users, f_coprs, f_copr_more_permissions,
            f_users_api, f_db):
        self.app.config['SEND_EMAILS'] = True

        u = User.query.filter_by(username='user1').first()
        perms = {'user4': {'admin': 'approved'}}
        r = self.auth_post("/set/user2/barcopr", perms, u)

        msg = (
            "[Copr] user2/barcopr: Your permissions have changed\n\n"
            "Your permissions have changed:\n\n"
            "Admin: nothing -> approved\n\n"
            "Project: user2/barcopr")

        assert len(send_mail.call_args_list) == 1
        assert str(send_mail.call_args_list[0][0][1]) == msg

    @patch('coprs.views.apiv3_ns.apiv3_permissions.send_mail',
           new_callable=MagicMock())
    def test_perms_set_sends_emails(
            self, send_mail, f_users, f_coprs, f_copr_more_permissions,
            f_users_api, f_db):
        self.app.config['SEND_EMAILS'] = True

        # u4 is only a builder in c3 so far, request admin!  but owner of c3 is
        # u2, and one additional admin u1 (two messages)
        u = User.query.filter_by(username='user4').first()
        permissions = {'admin': True}
        r = self.auth_post('/request/user2/barcopr', permissions, u)
        assert r.status_code == 200

        msg = "\n\n".join([
            "[Copr] user2/barcopr: user4 is requesting permissions change",
            "user4 asked for these changes:",
            "Admin: nothing -> request",
            "Project: user2/barcopr"])

        emails = ['user1@spam.foo', 'user2@spam.foo']
        calls = send_mail.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == "user2@spam.foo"
        assert calls[1][0][0] == "user1@foo.bar"
        assert str(calls[0][0][1]) == msg
        assert str(calls[1][0][1]) == msg

        # re-request without errors, but no new mail!
        u = User.query.filter_by(username='user4').first()
        permissions = {'admin': True}
        r = self.auth_post('/request/user2/barcopr', permissions, u)
        assert r.status_code == 200
        assert len(calls) == 2
