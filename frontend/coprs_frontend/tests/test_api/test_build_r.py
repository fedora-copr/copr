# coding: utf-8

import json
from marshmallow import pprint

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestBuildResource(CoprsTestCase):

    def test_collection_ok(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        # project_id = self.c1.id

        href = "/api_2/builds/chroots"
        expected_len = len(self.basic_builds)
        self.db.session.commit()
        r = self.tc.get(href)

    def test_collection_ok_by_username(
            self, f_users, f_coprs, f_builds, f_db,
            f_users_api, f_mock_chroots):

        # project_id = self.c1.id

        href = "/api_2/builds?owner={}".format(self.u1.username)
        expected_len = 2
        self.db.session.commit()
        r = self.tc.get(href)
