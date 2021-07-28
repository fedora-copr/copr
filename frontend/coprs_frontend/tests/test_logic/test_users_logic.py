import json
from coprs import app
from coprs.logic.users_logic import UserDataDumper, UsersLogic
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


app.config["SERVER_NAME"] = "localhost.localdomain"


class TestUserDataDumper(CoprsTestCase):

    def test_user_information(self, f_users, f_fas_groups, f_coprs, f_db):
        dumper = UserDataDumper(self.u1)
        data = dumper.user_information
        assert data["username"] == "user1"
        assert data["email"] == "user1@foo.bar"
        assert data["timezone"] is None
        assert data["api_login"] == "abc"
        assert data["api_token"] == "abc"
        assert data["api_token_expiration"] == "Jan 01 2000 00:00:00"
        assert data["gravatar"].startswith("https://seccdn.libravatar.org/avatar/")

    def test_projects(self, f_users, f_coprs, f_db):
        app.config["SERVER_NAME"] = "localhost.localdomain"
        with app.app_context():
            dumper = UserDataDumper(self.u1)
            projects = dumper.projects
            assert [p["full_name"] for p in projects] == ["user1/foocopr"]

    def test_builds(self, f_users, f_coprs, f_builds, f_db):
        app.config["SERVER_NAME"] = "localhost.localdomain"
        with app.app_context():
            dumper = UserDataDumper(self.u1)
            builds = dumper.builds
            assert len(builds) == 1
            assert builds[0]["id"] == 1
            assert builds[0]["project"] == "user1/foocopr"

    def test_data(self, f_users, f_fas_groups, f_coprs, f_db):
        app.config["SERVER_NAME"] = "localhost.localdomain"
        with app.app_context():
            dumper = UserDataDumper(self.u1)
            data = dumper.data
            assert "username" in data
            assert type(data["groups"]) == list
            assert type(data["projects"]) == list
            assert type(data["builds"]) == list

    def test_dumps(self, f_users, f_fas_groups, f_coprs, f_db):
        app.config["SERVER_NAME"] = "localhost.localdomain"
        with app.app_context():
            dumper = UserDataDumper(self.u1)
            output = dumper.dumps()
            assert type(output) == str
            data = json.loads(output)
            assert "username" in data
            assert "projects" in data


class TestUserDelete(CoprsTestCase):

    def test_delete_user_data(self, f_users, f_fas_groups, f_coprs, f_db):
        UsersLogic.delete_user_data(self.u1)
        self.db.session.commit()
        user = UsersLogic.get(self.u1.username).one()
        assert not user.admin
        assert not user.api_login

    @TransactionDecorator("u1")
    def test_delete_data_view(self, f_users, f_fas_groups, f_coprs, f_db):
        r = self.tc.get("/user/delete")
        user = UsersLogic.get(self.u1.username).one()
        assert not user.admin
        assert not user.api_login
