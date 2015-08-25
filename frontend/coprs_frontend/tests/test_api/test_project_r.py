# coding: utf-8

import base64
import json

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestProjectResource(CoprsTestCase):

    def test_self(self):
        href = "/api_2/projects"
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data)
        assert obj["_links"]["self"]["href"] == href

    @TransactionDecorator("u1")
    def test_create_new(self, f_users, f_mock_chroots, f_db, f_users_api):
        self.db.session.add_all([self.u1, self.mc1])

        chroot_name = self.mc1.name
        body = {
            "name": "test_copr",
            "chroots": [
                chroot_name,
            ],
            "additional_repos": ["copr://bar/zar", ]
        }

        r = self.request_rest_api_with_auth("/api_2/projects", content=body, method="post")
        assert r.status_code == 201
        copr_dict = json.loads(r.data)
        assert copr_dict["copr"]["id"] == 1
        r2 = self.tc.get("/api_2/projects/1/chroots")
        copr_chroots_dict = json.loads(r2.data)
        assert len(copr_chroots_dict["chroots"]) == 1
        assert copr_chroots_dict["chroots"][0]["chroot"]["name"] == chroot_name

