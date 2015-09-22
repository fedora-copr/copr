# coding: utf-8
import copy

import json
from marshmallow import pprint

import pytest
import sqlalchemy
from coprs.helpers import StatusEnum

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestBuildTaskResource(CoprsTestCase):

    def test_collection_ok(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):

        href = "/api_2/build_tasks?build_id=1"
        bc_list = copy.deepcopy(self.b1_bc)

        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data.decode("utf-8"))
        assert len(obj["build_tasks"]) == len(bc_list)

    def test_collection_ok_default_limit(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):

        self.db.session.commit()
        href_tpl = "/api_2/build_tasks?limit={}"
        expected = href_tpl.format(100)

        for val in [-1, 0, 100, 105, 1000]:
            href = href_tpl.format(val)

            r0 = self.tc.get(href)
            assert r0.status_code == 200
            obj = json.loads(r0.data.decode("utf-8"))
            assert obj["_links"]["self"]["href"] == expected

    def test_collection_ok_by_state(
            self, f_users, f_coprs,
            f_mock_chroots_many,
            f_build_many_chroots,
            f_db,
            f_users_api):

        self.db.session.commit()
        for status in StatusEnum.vals.values():
            expected_chroots = set([
                name
                for name, chroot_status in
                self.status_by_chroot.items()
                if chroot_status == status
            ])

            href = "/api_2/build_tasks?state={}&limit=50".format(StatusEnum(status))

            r0 = self.tc.get(href)
            assert r0.status_code == 200
            obj = json.loads(r0.data.decode("utf-8"))
            assert len(obj["build_tasks"]) == len(expected_chroots)
            assert set(bt["build_task"]["chroot_name"]
                       for bt in obj["build_tasks"]) == expected_chroots
            assert obj["_links"]["self"]["href"] == href

    def test_collection_ok_by_project(
            self, f_users, f_coprs, f_mock_chroots, f_builds,
           f_users_api, f_db):

        href = "/api_2/build_tasks?project_id=1&limit=50"
        bc_list = copy.deepcopy(self.b1_bc)
        bc_list.extend(copy.deepcopy(self.b2_bc))

        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data.decode("utf-8"))
        assert len(obj["build_tasks"]) == len(bc_list)
        assert obj["_links"]["self"]["href"] == href

    def test_collection_ok_by_owner(
            self, f_users, f_coprs, f_mock_chroots, f_builds,
           f_users_api, f_db):

        href = "/api_2/build_tasks?owner={}&limit=50".format(self.u2.username)
        bc_list_len = sum(
            len(b.build_chroots)
            for b in self.basic_builds
            if b.copr.owner == self.u2
        )

        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data.decode("utf-8"))
        assert len(obj["build_tasks"]) == bc_list_len
        assert obj["_links"]["self"]["href"] == href

    def test_post_not_allowed(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/build_tasks",
            method="post",
            content={},
        )
        assert r0.status_code == 405

    def test_get_one(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):
        expected_fields = [
            ("state", None),
            ("git_hash", None),
            ("started_on", None),
            ("ended_on", None),
            ("name", "chroot_name"),
        ]
        bc = self.b1_bc[0]
        expected_dict = {
            f: getattr(bc, f)
            for f, _ in expected_fields
        }
        href = "/api_2/build_tasks/1/{}".format(bc.name)
        self.db.session.commit()

        r0 = self.tc.get(href)
        assert r0.status_code == 200
        obj = json.loads(r0.data.decode("utf-8"))
        for k, res_k in expected_fields:
            if res_k is None:
                res_k = k
            assert obj["build_task"][res_k] == expected_dict[k]

    def test_get_one_bad_name(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db,
                           f_users_api):

        href = "/api_2/build_tasks/1/surely_bad_chroot_name"
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


