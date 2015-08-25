# coding: utf-8

import base64
import json

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestProjectChrootResource(CoprsTestCase):
    def test_remove_chroot(self, f_users, f_coprs,f_db, f_users_api,
                           f_mock_chroots_many, f_build_few_chroots):

        chroot_name = self.mc_list[0].name
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data)["chroots"]) == len(self.mc_list)

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="delete")

        assert r1.status_code == 204

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data)["chroots"]) == len(self.mc_list) - 1

    def test_remove_chroot_other_user(
            self, f_users, f_coprs,f_db, f_users_api,
            f_mock_chroots_many, f_build_few_chroots):

        chroot_name = self.mc_list[0].name
        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data)["chroots"]) == len(self.mc_list)

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            login=login, token=token,
            method="delete")

        assert r1.status_code == 403

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data)["chroots"]) == len(self.mc_list)
