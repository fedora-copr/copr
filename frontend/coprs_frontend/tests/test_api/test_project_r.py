# coding: utf-8

import base64
import copy
import json
from marshmallow import pprint

import pytest
import sqlalchemy
from coprs.logic.builds_logic import BuildsLogic

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.models import Copr

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestProjectResource(CoprsTestCase):
    put_update_dict = {
        "description": "foo bar",
        "instructions": "cthulhu fhtagn",
        "repos": [
            "http://example.com/repo",
            "copr://foo/bar"
            "copr://g/foo/bar"
        ],
        "disable_createrepo": True,
        "build_enable_net": False,
        "homepage": "http://example.com/foobar",
        "contact": "foo@example.com",
    }

    def test_project_list_self(self):
        href = "/api_2/projects"
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert obj["_links"]["self"]["href"] == href

    def test_project_list_all(self, f_users, f_mock_chroots, f_coprs, f_db):
        expected_id_set = set(c.id for c in self.basic_coprs_list)
        href = "/api_2/projects"
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert set(p["project"]["id"] for p in obj["projects"]) == \
            expected_id_set

    def test_project_list_by_user(self, f_users, f_mock_chroots, f_coprs, f_db):
        expected_id_set = set(
            c.id for c in self.basic_coprs_list
            if c.owner == self.u1
        )
        href = "/api_2/projects?owner={}".format(self.u1.username)
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert set(p["project"]["id"] for p in obj["projects"]) == \
            expected_id_set

    def test_project_list_by_name(self, f_users, f_mock_chroots, f_coprs, f_db):
        expected_id_set = set(
            c.id for c in self.basic_coprs_list
            if c.name == self.c1.name
        )
        href = "/api_2/projects?name={}".format(self.c1.name)
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert set(p["project"]["id"] for p in obj["projects"]) == \
            expected_id_set

    def test_project_list_limit_offset(self, f_users, f_mock_chroots, f_coprs, f_db):
        # quite hardcoded test
        s_1 = set(p.id for p in [self.c1, self.c2])
        s_2 = set(p.id for p in [self.c2, self.c3])
        s_3 = set(p.id for p in [self.c3])

        href_list = [
            "/api_2/projects?limit=2",
            "/api_2/projects?limit=2&offset=1",
            "/api_2/projects?limit=2&offset=2"
        ]
        for href, expected in zip(href_list, [s_1, s_2, s_3]):
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))
            assert set(p["project"]["id"] for p in obj["projects"]) == \
                expected

    def test_project_list_search(self, f_users, f_mock_chroots, f_coprs, f_db):
        self.prefix = u"prefix"
        self.s_coprs = []
        c1_username = self.c1.owner.username

        k1 = 3
        k2 = 5
        for x in range(k1):
            self.s_coprs.append(Copr(name=self.prefix + str(x), owner=self.u1))

        for x in range(k2):
            self.s_coprs.append(Copr(name=self.prefix + str(x), owner=self.u2))

        self.db.session.add_all(self.s_coprs)
        self.db.session.commit()

        r0 = self.tc.get(u"/api_2/projects?search_query={}".format(self.prefix))
        assert r0.status_code == 200
        obj = json.loads(r0.data.decode("utf-8"))
        assert len(obj["projects"]) == k1 + k2
        for p in obj["projects"]:
            assert self.prefix in p["project"]["name"]

        r1 = self.tc.get(u"/api_2/projects?search_query={}&owner={}"
                         .format(self.prefix, c1_username))
        assert r1.status_code == 200
        obj = json.loads(r1.data.decode("utf-8"))
        assert len(obj["projects"]) == k1
        for p in obj["projects"]:
            assert self.prefix in p["project"]["name"]

    def test_project_create_new(self, f_users, f_mock_chroots, f_users_api):
        self.db.session.add_all([self.u1, self.mc1])
        self.db.session.commit()

        chroot_name = self.mc1.name
        body = {
            "name": "test_copr",
            "chroots": [
                chroot_name,
            ],
            "repos": ["copr://bar/zar", ]
        }

        r = self.request_rest_api_with_auth(
            "/api_2/projects",
            content=body, method="post")
        assert r.status_code == 201
        assert r.headers["Location"].endswith("/api_2/projects/1")

        r2 = self.tc.get("/api_2/projects/1/chroots")
        copr_chroots_dict = json.loads(r2.data.decode("utf-8"))
        assert len(copr_chroots_dict["chroots"]) == 1
        assert copr_chroots_dict["chroots"][0]["chroot"]["name"] == chroot_name

    def test_project_create_bad_json(self, f_users, f_mock_chroots, f_users_api, f_db):
        r = self.request_rest_api_with_auth(
            "/api_2/projects",
            data="fdf{fsd",
            method="post")

        assert r.status_code == 400

    def test_project_create_bad_values(
            self, f_users, f_mock_chroots,
            f_users_api, f_db):

        href = "/api_2/projects"
        cases = []

        def add_case(field, value):
            t = copy.deepcopy(self.put_update_dict)

            t["name"] = "foobar_fake"
            t["chroots"] = [mc.name for mc in self.mc_basic_list]

            t[field] = value
            cases.append(t)

        add_case("repos", "foobar")
        add_case("repos", 1)
        add_case("contact", "adsg")
        add_case("contact", "1")
        add_case("homepage", "sdg")

        add_case("name", None)
        add_case("name", "")
        add_case("name", "3abc")
        add_case("chroots", "sdg")
        add_case("chroots", "")

        for test_case in cases:
            r0 = self.request_rest_api_with_auth(
                href,
                method="post",
                content=test_case
            )
            assert r0.status_code == 400

    def test_project_create_ok_values(
            self, f_users, f_mock_chroots,
            f_users_api, f_db):

        href = "/api_2/projects"
        cases = []

        self.counter = 0

        def add_case(field, value):
            t = copy.deepcopy(self.put_update_dict)
            t["name"] = "foobar_{}".format(self.counter)
            t["chroots"] = [mc.name for mc in self.mc_basic_list]
            self.counter += 1

            t[field] = value
            cases.append(t)

        add_case("repos", [])
        add_case("repos", None)
        add_case("contact", "")
        add_case("contact", None)
        add_case("contact", "foo@bar.com")
        add_case("homepage", "http://foo.org/bar/xdeeg?sdfg")

        add_case("name", "asdas-asdf")
        add_case("name", "a2222222")
        add_case("chroots", [])

        for test_case in cases:
            r0 = self.request_rest_api_with_auth(
                href,
                method="post",
                content=test_case
            )
            assert r0.status_code == 201

    def test_project_create_new_project_exists(
            self, f_users, f_mock_chroots, f_coprs, f_users_api):
        self.db.session.add_all([self.u1, self.mc1])
        self.db.session.commit()

        chroot_name = self.mc1.name
        body = {
            "name": self.c1.name,
            "chroots": [
                chroot_name,
            ],
            "repos": ["copr://bar/zar", ]
        }
        r = self.request_rest_api_with_auth(
            "/api_2/projects",
            content=body, method="post")
        assert r.status_code == 409

    def test_project_get_one_not_found(self, f_users, f_mock_chroots, f_db):
        r = self.tc.get("/api_2/projects/1")
        assert r.status_code == 404

    def test_project_get_one(self, f_users, f_mock_chroots, f_coprs, f_db):

        p_id_list = [p.id for p in self.basic_coprs_list]
        for p_id in p_id_list:
            href = "/api_2/projects/{}".format(p_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))

            assert obj["project"]["id"] == p_id
            assert obj["_links"]["self"]["href"] == href

    def test_project_get_one_with_chroots(self, f_users, f_mock_chroots, f_coprs, f_db):

        p_id_list = [p.id for p in self.basic_coprs_list]
        for p_id in p_id_list:
            href = "/api_2/projects/{}?show_chroots=True".format(p_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))

            assert obj["project"]["id"] == p_id
            assert obj["_links"]["self"]["href"] == href
            project = CoprsLogic.get_by_id(p_id).one()
            assert len(obj["project_chroots"]) == len(project.copr_chroots)

    def test_project_get_one_with_builds(
            self, f_users, f_mock_chroots,
            f_coprs, f_builds, f_db):

        p_id_list = [p.id for p in self.basic_coprs_list]
        for p_id in p_id_list:
            href = "/api_2/projects/{}?show_builds=True".format(p_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))

            assert obj["project"]["id"] == p_id
            assert obj["_links"]["self"]["href"] == href
            project = CoprsLogic.get_by_id(p_id).one()
            builds = BuildsLogic.get_multiple_by_copr(project).all()
            assert len(obj["project_builds"]) == len(builds)

    def test_project_delete_not_found(
            self, f_users, f_mock_chroots,
            f_users_api, f_db):

        href = "/api_2/projects/{}".format("1")

        r0 = self.request_rest_api_with_auth(
            href,
            method="delete"
        )
        assert r0.status_code == 404

    def test_project_delete_ok(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):

        href = "/api_2/projects/{}".format(self.c1.id)

        r0 = self.request_rest_api_with_auth(
            href,
            method="delete"
        )
        assert r0.status_code == 204
        assert self.tc.get(href).status_code == 404

    def test_project_delete_fail_unfinished_build(
            self, f_users, f_mock_chroots,
            f_coprs, f_builds, f_users_api, f_db):

        href = "/api_2/projects/{}".format(self.c1.id)

        r0 = self.request_rest_api_with_auth(
            href,
            method="delete"
        )
        assert r0.status_code == 400

    def test_project_delete_fail_unfinished_project_action(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):

        CoprsLogic.create_delete_action(self.c1)
        self.db.session.commit()
        href = "/api_2/projects/{}".format(self.c1.id)
        r0 = self.request_rest_api_with_auth(
            href,
            method="delete"
        )
        assert r0.status_code == 400

    def test_project_delete_wrong_user(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):

        login = self.u2.api_login
        token = self.u2.api_token

        href = "/api_2/projects/{}".format(self.c1.id)

        r0 = self.request_rest_api_with_auth(
            href,
            method="delete",
            login=login, token=token,
        )
        assert r0.status_code == 403

    def test_project_put_ok(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):

        href = "/api_2/projects/{}".format(self.c1.id)
        r0 = self.request_rest_api_with_auth(
            href,
            method="put",
            content=self.put_update_dict
        )
        assert r0.status_code == 204

        r1 = self.tc.get(href)
        obj = json.loads(r1.data.decode("utf-8"))
        updated_project = obj["project"]
        for k, v in self.put_update_dict.items():
            assert updated_project[k] == v

    def test_project_put_wrong_user(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):
        login = self.u2.api_login
        token = self.u2.api_token

        href = "/api_2/projects/{}".format(self.c1.id)
        r0 = self.request_rest_api_with_auth(
            href,
            method="put",
            content=self.put_update_dict,
            login=login, token=token,
        )
        assert r0.status_code == 403

    def test_project_put_not_found(
            self, f_users, f_mock_chroots, f_users_api, f_db):

        href = "/api_2/projects/1"
        r0 = self.request_rest_api_with_auth(
            href,
            method="put",
            content=self.put_update_dict,
        )
        assert r0.status_code == 404

    def test_project_put_bad_values(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):
        href = "/api_2/projects/{}".format(self.c1.id)
        cases = []

        def add_case(field, value):
            t = copy.deepcopy(self.put_update_dict)
            t[field] = value
            cases.append(t)

        add_case("repos", "foobar")
        add_case("repos", 1)
        add_case("contact", "adsg")
        add_case("contact", "1")
        add_case("homepage", "sdg")

        for test_case in cases:
            r0 = self.request_rest_api_with_auth(
                href,
                method="put",
                content=test_case
            )
            assert r0.status_code == 400

    def test_project_put_ok_values(
            self, f_users, f_mock_chroots,
            f_coprs, f_users_api, f_db):
        href = "/api_2/projects/{}".format(self.c1.id)
        cases = []

        def add_case(field, value):
            t = copy.deepcopy(self.put_update_dict)
            t[field] = value
            cases.append(t)

        add_case("repos", [])
        add_case("repos", None)
        add_case("contact", "")
        add_case("contact", None)
        add_case("contact", "foo@bar.com")
        add_case("homepage", "http://foo.org/bar/xdeeg?sdfg")

        for test_case in cases:
            r0 = self.request_rest_api_with_auth(
                href,
                method="put",
                content=test_case
            )
            assert r0.status_code == 204
