import copy
import datetime
import json
from unittest.mock import patch, MagicMock

import pytest

from coprs.models import User, Copr

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestApiv3Projects(CoprsTestCase):
    def test_get_project_list_order(self, f_users, f_coprs, f_mock_chroots,
                                    f_copr_more_permissions, f_users_api, f_db):


        url = "/api_3/project/list?order=id&order_type=DESC"
        response = self.tc.get(url)
        projects1 = response.json["items"]
        assert [p["id"] for p in projects1] == [3, 2, 1]

        url = "/api_3/project/list?order=name&order_type=DESC"
        response = self.tc.get(url)
        projects2 = response.json["items"]
        assert [p["id"] for p in projects2] == [2, 1, 3]

        url = "/api_3/project/list?order=name&order_type=ASC"
        response = self.tc.get(url)
        projects3 = response.json["items"]
        assert [p["id"] for p in projects3] == [3, 1, 2]
        assert projects3 == list(reversed(projects2))

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("store, read", [(True, "on"), (False, "off")])
    def test_compat_bootstrap_config(self, store, read):
        route = "/api_3/project/add/{}".format(self.transaction_username)
        self.api3.post(route, {
            "name": "test-compat-bootstrap",
            "chroots": ["fedora-rawhide-i386"],
            "use_bootstrap_container": store,
        })
        assert Copr.query.one().bootstrap == read

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("store, read", [("nspawn", "nspawn"), ("simple", "simple"), (None, "default")])
    def test_isolation_config(self, store, read):
        route = "/api_3/project/add/{}".format(self.transaction_username)
        data = {
            "name": "test-isolation",
            "chroots": ["fedora-rawhide-i386"],
            "isolation": store,
        }
        if store is None:
            del data["isolation"]
        self.api3.post(route, data)
        assert Copr.query.one().isolation == read

    def _get_copr_id_data(self, copr_id):
        data = copy.deepcopy(self.models.Copr.query.get(copr_id).__dict__)
        data.pop("_sa_instance_state")
        data.pop("latest_indexed_data_update")
        return data

    @pytest.mark.usefixtures("f_u1_ts_client", "f_mock_chroots", "f_db")
    def test_update_copr_api3(self):
        self.api3.new_project("test", ["fedora-rawhide-i386"],
                              bootstrap="default", isolation="simple",
                              contact="somebody@redhat.com",
                              homepage="https://github.com/fedora-copr",
                              appstream=True)
        old_data = self._get_copr_id_data(1)

        # When new arguments are added to the Copr model, we should update this
        # testing method!
        already_tested = set([
            "delete_after", "build_enable_net", "auto_createrepo", "repos",
            "runtime_dependencies", "packit_forge_projects_allowed"
        ])

        # check non-trivial changes
        assert old_data["delete_after"] is None
        assert old_data["build_enable_net"] is False
        assert old_data["auto_createrepo"] is True
        assert old_data["module_hotfixes"] is False
        assert old_data["fedora_review"] is False
        assert old_data["repos"] == ''
        assert old_data["runtime_dependencies"] == ""
        assert old_data["auto_prune"] is True
        assert old_data["follow_fedora_branching"] is True
        assert old_data["packit_forge_projects_allowed"] == ""
        self.api3.modify_project(
            "test", delete_after_days=5, enable_net=True, devel_mode=True,
            repos=["http://example/repo/", "http://another/"],
            runtime_dependencies=["http://run1/repo/", "http://run2/"],
            bootstrap_image="noop", appstream=True,
            packit_forge_projects_allowed=[
                "https://github.com/packit/ogr",
                "github.com/packit/requre",
                "http://github.com/packit/packit"
            ]
        )
        new_data = self._get_copr_id_data(1)
        delete_after = datetime.datetime.now() + datetime.timedelta(days=5)
        assert new_data["delete_after"] > delete_after
        old_data["delete_after"] = new_data["delete_after"]
        old_data["build_enable_net"] = True
        old_data["auto_createrepo"] = False
        old_data["repos"] = "http://example/repo/\nhttp://another/"
        old_data["runtime_dependencies"] = "http://run1/repo/\nhttp://run2/"
        old_data["bootstrap"] = "default"
        old_data["packit_forge_projects_allowed"] = "github.com/packit/ogr\ngithub.com/packit/requre\ngithub.com" \
                                                    "/packit/packit"
        assert old_data == new_data
        old_data = new_data

        easy_changes = [{
            "isolation": "nspawn",
        }, {
            "isolation": "default",
        }, {
            "description": "simple desc",
        }, {
            "instructions": "how to enable",
        }, {
            "homepage": "https://example.com/blah/",
        }, {
            "contact": "jdoe@example.com",
        }, {
            "unlisted_on_hp": True,
        }, {
            "bootstrap": "off",
        }, {
            "multilib": True,
        }, {
            "module_hotfixes": True,
        }, {
            "auto_prune": True,
        }, {
            "auto_prune": False,
        }, {
            "fedora_review": True,
        }, {
            "follow_fedora_branching": False,
        }, {
            "follow_fedora_branching": True,
        }, {
        }, {
            "appstream": True,
        }]

        for setup in easy_changes:
            for key in setup:
                already_tested.add(key)

        should_test = {c.name for c in self.models.Copr.__table__.columns}

        # these are never meant to be changed by modify
        for item in [
            "created_on", "deleted", "scm_api_auth_json", "scm_api_type",
            "scm_repo_url", "id", "name", "user_id", "group_id",
            "webhook_secret", "forked_from_id", "latest_indexed_data_update",
            "copr_id", "persistent", "playground",
        ]:
            should_test.remove(item)

        assert already_tested == should_test

        for case in easy_changes:
            self.api3.modify_project("test", **case)
            new_data = self._get_copr_id_data(1)
            old_data.update(**case)
            assert old_data == new_data
            old_data = new_data

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_users_api", "f_mock_chroots", "f_db")
    def test_fedora_review_setting(self):
        """
        Make sure that `fedora_review` setting is not lost when we modify
        project without specifying it.
        """
        self.db.session.add(self.c1)
        copr = Copr.query.get(self.c1.id)
        assert not copr.fedora_review
        assert not copr.delete_after_days

        route = "/api_3/project/edit/{}".format(self.c1.full_name)
        self.api3.post(route, {"fedora_review": True})
        assert Copr.query.get(self.c1.id).fedora_review

        self.api3.post(route, {"delete_after_days": 5})
        copr = Copr.query.get(self.c1.id)
        assert copr.fedora_review
        assert copr.delete_after_days == 5

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_users_api", "f_mock_chroots", "f_db")
    def test_regenerate_repos(self):
        """
        Make sure that the regenerate-repos api works.
        """
        self.db.session.add(self.c1)
        route = "/api_3/project/regenerate-repos/{}".format(self.c1.full_name)
        r = self.api3.post(route, {})
        assert r.status_code == 200


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
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_copr_more_permissions",
                             "f_users_api", "f_db")
    def test_perms_set_sends_emails_2(self, send_mail):
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

        calls = send_mail.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == ["user2@spam.foo"]
        assert calls[1][0][0] == ["user1@foo.bar"]
        assert str(calls[0][0][1]) == msg
        assert str(calls[1][0][1]) == msg

        # re-request without errors, but no new mail!
        u = User.query.filter_by(username='user4').first()
        permissions = {'admin': True}
        r = self.auth_post('/request/user2/barcopr', permissions, u)
        assert r.status_code == 200
        assert len(calls) == 2
