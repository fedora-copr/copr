# coding: utf-8
import copy

import json
from marshmallow import pprint

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestBuildChrootResource(CoprsTestCase):

    def test_collection_ok(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):

        # project_id = self.c1.id
        # import ipdb; ipdb.set_trace()
        href = "/api_2/builds/1/chroots"
        bc_list = copy.deepcopy(self.b1_bc)

        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data)
        assert len(obj["chroots"]) == len(bc_list)
        assert obj["_links"]["self"]["href"] == href

    def test_post_not_allowed(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds/1/chroots",
            method="post",
            content={},
        )
        assert r0.status_code == 405

    def test_get_one(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):
        expected_fields = [
            "state",
            "git_hash",
            "started_on",
            "ended_on",
            "name"
        ]
        bc = self.b1_bc[0]
        expected_dict = {
            f: getattr(bc, f)
            for f in expected_fields
        }
        href = "/api_2/builds/1/chroots/{}".format(bc.name)
        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data)
        assert obj["chroot"] == expected_dict

    def test_get_one_bad_name(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):

        href = "/api_2/builds/1/chroots/surely_bad_chroot_name"
        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 400

    def get_test_not_found(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db, f_users_api):

        bc = self.b1_bc[0]
        href = "/api_2/builds/48545656/chroots/{}".format(bc.name)
        href2 = "/api_2/builds/1/chroots/{}".format(bc.name)
        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 404

        r1 = self.tc.get(href2)
        assert r1.status_code == 404


    # def test_put_cancel_build_chroot


