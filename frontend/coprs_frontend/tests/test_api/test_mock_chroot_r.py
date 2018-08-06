# coding: utf-8

import json
from marshmallow import pprint

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestMockChrootResource(CoprsTestCase):

    def test_collection(self, f_mock_chroots, f_db):
        href = "/api_2/mock_chroots"
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert obj["_links"]["self"]["href"] == href
        assert len(obj["chroots"]) == len(self.mc_basic_list)

    def test_collection_only_active(self, f_mock_chroots, f_db):
        expected_len = len(self.mc_basic_list) - 1
        self.mc4.is_active = False
        self.db.session.add(self.mc4)
        self.db.session.commit()

        href = "/api_2/mock_chroots?active_only=True"
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert obj["_links"]["self"]["href"] == href
        assert len(obj["chroots"]) == expected_len

    def test_post_not_allowed(self, f_mock_chroots, f_db, f_users, f_users_api):
        r0 = self.request_rest_api_with_auth(
            "/api_2/mock_chroots",
            method="post",
            content={},
        )
        assert r0.status_code == 405

    def test_get_one(self, f_mock_chroots, f_db):
        chroot_name = self.mc1.name
        href = "/api_2/mock_chroots/{}".format(chroot_name)
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert obj["_links"]["self"]["href"] == href
        assert obj["chroot"]["name"] == chroot_name
