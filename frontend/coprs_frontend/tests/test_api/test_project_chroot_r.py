# coding: utf-8

import base64
import copy
import json

import pytest
import sqlalchemy

from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestProjectChrootResource(CoprsTestCase):
    def test_remove_chroot(self, f_users, f_coprs, f_db, f_users_api,
                           f_mock_chroots_many):

        init_len = len([mc for mc in self.mc_list if mc.is_active])
        chroot_name = self.mc_list[0].name
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == init_len

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="delete")

        assert r1.status_code == 204

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == init_len - 1

        # test idempotency
        r3 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="delete")

        assert r3.status_code == 204
        r4 = self.tc.get("/api_2/projects/1/chroots")
        assert r4.status_code == 200
        assert len(json.loads(r4.data.decode("utf-8"))["chroots"]) == init_len - 1

    def test_remove_chroot_other_user(
            self, f_users, f_coprs,f_db, f_users_api,
            f_mock_chroots_many, f_build_few_chroots):

        init_len = len([mc for mc in self.mc_list if mc.is_active])
        chroot_name = self.mc_list[0].name
        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == init_len

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            login=login, token=token,
            method="delete")

        assert r1.status_code == 403

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == init_len

    def test_put_correct(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        chroot_name = self.mc1.name
        self.db.session.commit()

        data = {
            "buildroot_pkgs": ["foo", "bar"],
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="put",
            content=data
        )
        assert r1.status_code == 200
        r2 = self.tc.get("/api_2/projects/1/chroots/{}".format(chroot_name))
        assert r2.status_code == 200

        def assert_content(response_data):
            for k, v in data.items():
                assert response_data.get(k) == v

        assert_content(json.loads(r2.data.decode("utf-8"))["chroot"])

        # test idempotency
        self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="put",
            content=data
        )
        r3 = self.tc.get("/api_2/projects/1/chroots/{}".format(chroot_name))
        assert r3.status_code == 200
        assert_content(json.loads(r3.data.decode("utf-8"))["chroot"])

        # test put with excessive name field
        data["name"] = chroot_name
        r4 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="put",
            content=data
        )
        assert r4.status_code == 200

    def test_put_erasing(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        chroot_name = self.mc1.name
        self.db.session.commit()

        data = {
            "buildroot_pkgs": [],
            "comps": None,
            "comps_name": None,
        }

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="put",
            content=data
        )
        assert r1.status_code == 200
        r2 = self.tc.get("/api_2/projects/1/chroots/{}".format(chroot_name))
        assert r2.status_code == 200

        def assert_content(response_data):
            for k, v in data.items():
                assert response_data.get(k) == v

        assert_content(json.loads(r2.data.decode("utf-8"))["chroot"])

    def test_put_wrong_name(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        chroot_name = "completely_fake_chroot"
        self.db.session.commit()

        data = {
            "buildroot_pkgs": [],
            "comps": None,
            "comps_name": None,
        }

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            method="put",
            content=data
        )
        assert r1.status_code == 400

    def test_put_wrong_user(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        data = {
            "buildroot_pkgs": [],
            "comps": None,
            "comps_name": None,
        }

        chroot_name = self.mc1.name
        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots/{}".format(chroot_name),
            login=login, token=token,
            content=data,
            method="put")

        assert r1.status_code == 403

    def test_create_chroot(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        new_chroot_name = self.mc2.name

        base_data = {
            "buildroot_pkgs": ["foo", "bar"],
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }
        data = {
            "name": new_chroot_name,
        }
        data.update(base_data)
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots",
            method="post",
            content=data
        )
        assert r1.status_code == 201

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == 2

        r3 = self.tc.get(r1.headers["Location"])

        def assert_content(response_data):
            for k, v in base_data.items():
                assert response_data.get(k) == v

        assert_content(json.loads(r3.data.decode("utf-8"))["chroot"])

    def test_create_chroot_build_no_buildchroot(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        new_chroot_name = self.mc2.name

        base_data = {
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }
        data = {
            "name": new_chroot_name,
        }
        data.update(base_data)
        self.db.session.commit()

        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

    def test_create_chroot_missing_name(self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        base_data = {
            "buildroot_pkgs": ["foo", "bar"],
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }
        self.db.session.commit()
        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots",
            method="post",
            content=base_data
        )
        assert r1.status_code == 400

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == 1

    def test_create_chroot_non_existing_name(
            self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):

        new_chroot_name = "completely-fake-chroot"
        base_data = {
            "buildroot_pkgs": ["foo", "bar"],
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }
        data = {
            "name": new_chroot_name,
        }
        data.update(base_data)
        self.db.session.commit()
        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots",
            method="post",
            content=data
        )
        assert r1.status_code == 400

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == 1

    def test_create_conflict_existing(
            self, f_users, f_coprs, f_db, f_users_api, f_mock_chroots):
        new_chroot_name = self.mc1.name
        base_data = {
            "buildroot_pkgs": ["foo", "bar"],
            "comps": "<comps><group></group></comps>",
            "comps_name": "test.xml",
        }
        data = {
            "name": new_chroot_name,
        }
        data.update(base_data)
        self.db.session.commit()
        self.db.session.commit()
        r0 = self.tc.get("/api_2/projects/1/chroots")
        assert r0.status_code == 200
        assert len(json.loads(r0.data.decode("utf-8"))["chroots"]) == 1

        r1 = self.request_rest_api_with_auth(
            "/api_2/projects/1/chroots",
            method="post",
            content=data
        )
        assert r1.status_code == 409

        r2 = self.tc.get("/api_2/projects/1/chroots")
        assert r2.status_code == 200
        assert len(json.loads(r2.data.decode("utf-8"))["chroots"]) == 1

