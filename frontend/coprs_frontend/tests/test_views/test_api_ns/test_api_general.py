import base64
import json

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCreateCopr(CoprsTestCase):
    copr_name = "copr_api_1"
    instructions = "1234"
    description = "567890"
    repos = "http://example.com/repo"  # TODO: better response on on http:// entries
    initial_pkgs = "http://example.com/pkg.src.rpm"

    def post_api_with_auth(self, url, content):
        userstring = "{}:{}".format(self.u1.api_login, self.u1.api_token)
        base64string_user = base64.b64encode(userstring.encode("utf-8"))
        base64string = b"Basic " + base64string_user

        return self.tc.post(
            url,
            content_type="application/json",
            data=content,
            headers={
                "Authorization": base64string
            }
        )

    @TransactionDecorator("u1")
    def test_api_create_copr_ok_minimal(self, f_users, f_mock_chroots, f_db):
        self.db.session.add_all([self.u1, self.mc1])
        self.tc.post("/api/new/")

        content = {
            "name": self.copr_name,
            self.mc1.name: "y",
            # "repos": repos,
            # "initial_pkgs": initial_pkgs,
            # "description": description,
            # "instructions": instructions
        }
        content_encoded = json.dumps(content)

        with pytest.raises(sqlalchemy.orm.exc.NoResultFound):
            CoprsLogic.get(self.u1.name, self.copr_name).one()

        r = self.post_api_with_auth(
            "/api/coprs/{}/new/".format(self.u1.name),
            content_encoded
        )
        response = json.loads(r.data.decode("utf-8"))
        assert "New project was successfully created" in response["message"]

        copr = self.models.Copr.query.filter(self.models.Copr.name == self.copr_name).one()
        assert copr.name == self.copr_name
        assert [self.mc1.name] == [c.name for c in copr.active_chroots]
        assert copr.repos == ''
        assert copr.owner.id == self.u1.id
        assert copr.auto_createrepo

    @TransactionDecorator("u1")
    def test_api_create_copr_ok_all(self, f_users, f_mock_chroots, f_db):
        self.db.session.add_all([self.u1, self.mc1])
        self.tc.post("/api/new/")

        content = {
            "name": self.copr_name,
            self.mc1.name: "y",
            "repos": self.repos,
            "initial_pkgs": self.initial_pkgs,
            "description": self.description,
            "instructions": self.instructions
        }
        content_encoded = json.dumps(content)

        with pytest.raises(sqlalchemy.orm.exc.NoResultFound):
            CoprsLogic.get(self.u1.name, self.copr_name).one()

        r = self.post_api_with_auth(
            "/api/coprs/{}/new/".format(self.u1.name),
            content_encoded
        )
        response = json.loads(r.data.decode("utf-8"))
        assert "New project was successfully created" in response["message"]

        copr = self.models.Copr.query.filter(self.models.Copr.name == self.copr_name).one()
        assert copr.name == self.copr_name
        assert [self.mc1.name] == [c.name for c in copr.active_chroots]
        assert copr.repos == self.repos
        assert copr.owner.id == self.u1.id
        assert copr.description == self.description
        assert copr.instructions == self.instructions

    #
    # @TransactionDecorator("u1")
    # def test_copr_modify(self, f_users, f_mock_chroots, f_db):
    #     self.db.session.add_all([self.u1, self.mc1])
    #
    #
