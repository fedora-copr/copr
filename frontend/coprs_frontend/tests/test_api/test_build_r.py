# coding: utf-8
from cStringIO import StringIO

import json
from marshmallow import pprint
import math

import pytest
import sqlalchemy
from coprs.helpers import BuildSourceEnum

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestBuildResource(CoprsTestCase):

    @staticmethod
    def extract_build_ids(response_object):
        return set([
            b_dict["build"]["id"]
            for b_dict in response_object["builds"]
        ])

    def test_collection_ok(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        href = "/api_2/builds"
        self.db.session.commit()
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data)

        # not a pure test, but we test API here
        builds = BuildsLogic.get_multiple().all()
        expected_ids = set([b.id for b in builds])

        assert expected_ids == self.extract_build_ids(obj)

    def test_collection_by_owner(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        names_list = [user.username for user in self.basic_user_list]
        for user_name in names_list:
            href = "/api_2/builds?owner={}".format(user_name)
            self.db.session.commit()
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data)

            # not a pure test, but we test API here
            builds = [
                b for b in BuildsLogic.get_multiple().all()
                if b.copr.owner.username == user_name
            ]
            expected_ids = set([b.id for b in builds])
            assert expected_ids == self.extract_build_ids(obj)

    def test_collection_by_project_id(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        project_id_list = [copr.id for copr in self.basic_coprs_list]
        for id_ in project_id_list:
            href = "/api_2/builds?project_id={}".format(id_)
            self.db.session.commit()
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data)

            # not a pure test, but we test API here
            builds = [
                b for b in BuildsLogic.get_multiple().all()
                if b.copr.id == id_
            ]
            expected_ids = set([b.id for b in builds])
            assert expected_ids == self.extract_build_ids(obj)

    def test_collection_limit_offset(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):
        self.db.session.commit()
        builds = BuildsLogic.get_multiple().all()
        total = len(builds)

        # test limit
        for lim in range(1, total + 1):
            href = "/api_2/builds?limit={}".format(lim)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data)
            builds = obj["builds"]
            assert len(builds) == lim

            if lim > 2:
                delta = int(math.floor(lim / 2))
                href1 = "/api_2/builds?limit={}".format(delta)
                href2 = "/api_2/builds?limit={0}&offset={0}".format(delta)

                r1 = self.tc.get(href1)
                r2 = self.tc.get(href2)

                assert r1.status_code == 200
                assert r2.status_code == 200

                obj1 = json.loads(r1.data)
                obj2 = json.loads(r2.data)

                assert builds[:delta] == obj1["builds"]
                assert builds[delta:2 * delta] == obj2["builds"]

    # todo: implement
    def _test_post_json(
            self, f_users, f_coprs, f_builds, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):

        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "url": "http://example.com/mypkg.src.rpm",
            "chroots": chroot_name_list
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content=metadata
        )
        print(r0.data)
        assert r0.status_code == 201

    def test_post_multipart(
            self, f_users, f_coprs, f_builds, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):
        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "enable_net": True,
            "chroots": chroot_name_list
        }
        data = {
            "metadata": json.dumps(metadata),
            "srpm": (StringIO(u'my file contents'), 'hello world.src.rpm')
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 201
        r1 = self.tc.get(r0.headers["Location"])
        assert r1.status_code == 200
        build_obj = json.loads(r1.data)

        assert build_obj["build"]["source_type"] == BuildSourceEnum("srpm_upload")

        chroots_href = build_obj["_links"]["chroots"]["href"]
        r2 = self.tc.get(chroots_href)
        build_chroots_obj = json.loads(r2.data)
        build_chroots_names = set([bc["chroot"]["name"] for bc in
                                   build_chroots_obj["chroots"]])
        assert set(chroot_name_list) == build_chroots_names
        assert len(chroot_name_list) == len(build_chroots_obj["chroots"])

    def test_post_multipart_missing_file(
            self,f_users, f_coprs, f_builds, f_db,
            f_users_api, f_mock_chroots):

        metadata = {
            "enable_net": True
        }
        data = {
            "metadata": json.dumps(metadata),
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 400

    def test_post_multipart_missing_metadata(
            self,f_users, f_coprs, f_builds, f_db,
            f_users_api, f_mock_chroots):
        data = {
            "srpm": (StringIO(u'my file contents'), 'hello world.src.rpm')
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 400

    def test_get_one(self, f_users, f_coprs, f_builds, f_db,
                     f_users_api, f_mock_chroots):

        build_id_list = [b.id for b in self.basic_builds]
        self.db.session.commit()

        for b_id in build_id_list:
            href = "/api_2/builds/{}".format(b_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data)
            assert obj["build"]["id"] == b_id
            assert obj["_links"]["self"]["href"] == href
