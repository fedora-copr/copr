# coding: utf-8
from io import BytesIO
import json
import math
import random
from marshmallow import pprint

from coprs.helpers import BuildSourceEnum, StatusEnum
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic
from tests.coprs_test_case import CoprsTestCase


class TestBuildResource(CoprsTestCase):

    @staticmethod
    def extract_build_ids(response_object):
        return set([
            b_dict["build"]["id"]
            for b_dict in response_object["builds"]
        ])

    def test_build_collection_ok(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        href = "/api_2/builds"
        self.db.session.commit()
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))

        # not a pure test, but we test API here
        builds = BuildsLogic.get_multiple().all()
        expected_ids = set([b.id for b in builds])

        assert expected_ids == self.extract_build_ids(obj)

    def test_build_collection_ok_finished(
            self, f_users, f_coprs, f_mock_chroots,  f_builds, f_db):

        self.db.session.commit()

        href_a = "/api_2/builds?is_finished=True"
        href_b = "/api_2/builds?is_finished=False"

        r_a = self.tc.get(href_a)
        r_b = self.tc.get(href_b)

        assert r_a.status_code == 200
        assert r_b.status_code == 200
        obj_a = json.loads(r_a.data.decode("utf-8"))
        obj_b = json.loads(r_b.data.decode("utf-8"))

        builds = BuildsLogic.get_multiple().all()
        expected_ids_a = set([b.id for b in builds if b.ended_on is not None])
        expected_ids_b = set([b.id for b in builds if b.ended_on is None])

        assert expected_ids_a == self.extract_build_ids(obj_a)
        assert expected_ids_b == self.extract_build_ids(obj_b)

    def test_build_collection_by_owner(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        names_list = [user.username for user in self.basic_user_list]
        for user_name in names_list:
            href = "/api_2/builds?owner={}".format(user_name)
            self.db.session.commit()
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))

            # not a pure test, but we test API here
            builds = [
                b for b in BuildsLogic.get_multiple().all()
                if b.copr.owner.username == user_name
            ]
            expected_ids = set([b.id for b in builds])
            assert expected_ids == self.extract_build_ids(obj)

    def test_build_collection_by_project_id(
            self, f_users, f_mock_chroots, f_coprs,  f_builds, f_db):

        project_id_list = [copr.id for copr in self.basic_coprs_list]
        for id_ in project_id_list:
            href = "/api_2/builds?project_id={}".format(id_)
            self.db.session.commit()
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))

            # not a pure test, but we test API here
            builds = [
                b for b in BuildsLogic.get_multiple().all()
                if b.copr.id == id_
            ]
            expected_ids = set([b.id for b in builds])
            assert expected_ids == self.extract_build_ids(obj)

    def test_build_collection_limit_offset(
            self, f_users, f_mock_chroots, f_coprs, f_builds, f_db):

        self.db.session.commit()
        builds = BuildsLogic.get_multiple().all()
        total = len(builds)

        # test limit
        for lim in range(1, total + 1):
            href = "/api_2/builds?limit={}".format(lim)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))
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

                obj1 = json.loads(r1.data.decode("utf-8"))
                obj2 = json.loads(r2.data.decode("utf-8"))

                assert builds[:delta] == obj1["builds"]
                assert builds[delta:2 * delta] == obj2["builds"]

        # for coverage
        href = "/api_2/builds?limit={}".format(1000000)
        r = self.tc.get(href)
        assert r.status_code == 200

    def test_build_post_bad_content_type(
            self, f_users, f_coprs, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):
        chroot_name_list = [c.name for c in self.c1.active_chroots]
        self.db.session.commit()
        metadata = {
            "project_id": 1,
            "srpm_url": "http://example.com/mypkg.src.rpm",
            "chroots": chroot_name_list
        }
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="plain/test"
        )
        assert r0.status_code == 400

    def test_build_post_json_bad_url(
            self, f_users, f_coprs, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):
        chroot_name_list = [c.name for c in self.c1.active_chroots]
        for url in [None, "", "dsafasdga", "gopher://mp.src.rpm"]:
            metadata = {
                "project_id": 1,
                "srpm_url": url,
                "chroots": chroot_name_list
            }
            self.db.session.commit()
            r0 = self.request_rest_api_with_auth(
                "/api_2/builds",
                method="post",
                content=metadata
            )
            assert r0.status_code == 400

    def test_build_post_json(
            self, f_users, f_coprs, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):

        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "srpm_url": "http://example.com/mypkg.src.rpm",
            "chroots": chroot_name_list
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content=metadata
        )
        assert r0.status_code == 201
        r1 = self.tc.get(r0.headers["Location"])
        assert r1.status_code == 200
        build_obj = json.loads(r1.data.decode("utf-8"))
        build_dict = build_obj["build"]
        assert build_dict["source_metadata"]["url"] == \
            metadata["srpm_url"]
        assert build_dict["source_type"] == "srpm_link"

    def test_build_post_json_on_wrong_user(
            self, f_users, f_coprs, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):

        login = self.u2.api_login
        token = self.u2.api_token

        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "srpm_url": "http://example.com/mypkg.src.rpm",
            "chroots": chroot_name_list
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            login=login, token=token,
            content=metadata,
        )
        assert r0.status_code == 403

    def test_build_post_json_on_project_during_action(
            self, f_users, f_coprs, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):

        CoprsLogic.create_delete_action(self.c1)
        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "srpm_url": "http://example.com/mypkg.src.rpm",
            "chroots": chroot_name_list
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content=metadata,
        )
        assert r0.status_code == 400

    def test_build_post_multipart_wrong_user(
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
            "srpm": (BytesIO(b'my file contents'), 'hello world.src.rpm')
        }
        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            login=login, token=token,
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 403

    def test_build_post_multipart_on_project_during_action(
            self, f_users, f_coprs, f_builds, f_db, f_mock_chroots,
            f_mock_chroots_many, f_build_many_chroots,
            f_users_api):

        CoprsLogic.create_delete_action(self.c1)
        chroot_name_list = [c.name for c in self.c1.active_chroots]
        metadata = {
            "project_id": 1,
            "enable_net": True,
            "chroots": chroot_name_list
        }
        data = {
            "metadata": json.dumps(metadata),
            "srpm": (BytesIO(b'my file contents'), 'hello world.src.rpm')
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 400

    def test_build_post_multipart(
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
            "srpm": (BytesIO(b'my file contents'), 'hello world.src.rpm')
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
        build_obj = json.loads(r1.data.decode("utf-8"))

        assert build_obj["build"]["source_type"] == "srpm_upload"

        tasks_href = build_obj["_links"]["build_tasks"]["href"]
        r2 = self.tc.get(tasks_href)
        build_chroots_obj = json.loads(r2.data.decode("utf-8"))
        build_chroots_names = set([bc["build_task"]["chroot_name"] for bc in
                                   build_chroots_obj["build_tasks"]])
        assert set(chroot_name_list) == build_chroots_names
        assert len(chroot_name_list) == len(build_chroots_obj["build_tasks"])

    def test_build_post_multipart_missing_file(
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

    def test_build_post_multipart_missing_metadata(
            self,f_users, f_coprs, f_builds, f_db,
            f_users_api, f_mock_chroots):
        data = {
            "srpm": (BytesIO(b'my file contents'), 'hello world.src.rpm')
        }
        self.db.session.commit()
        r0 = self.request_rest_api_with_auth(
            "/api_2/builds",
            method="post",
            content_type="multipart/form-data",
            data=data
        )
        assert r0.status_code == 400

    def test_build_get_one(self, f_users, f_coprs, f_builds, f_db,
                     f_users_api, f_mock_chroots):

        build_id_list = [b.id for b in self.basic_builds]
        self.db.session.commit()

        for b_id in build_id_list:
            href = "/api_2/builds/{}".format(b_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))
            assert obj["build"]["id"] == b_id
            assert obj["_links"]["self"]["href"] == href

    def test_build_get_one_with_tasks(self, f_users, f_coprs, f_builds, f_db,
                     f_users_api, f_mock_chroots):

        build_id_list = [b.id for b in self.basic_builds]
        self.db.session.commit()

        for b_id in build_id_list:
            href = "/api_2/builds/{}?show_build_tasks=True".format(b_id)
            r = self.tc.get(href)
            assert r.status_code == 200
            obj = json.loads(r.data.decode("utf-8"))
            assert obj["build"]["id"] == b_id
            assert obj["_links"]["self"]["href"] == href
            assert "build_tasks" in obj

    def test_build_get_one_not_found(self, f_users, f_coprs, f_builds, f_db,
                     f_users_api, f_mock_chroots):
        build_id_list = [b.id for b in self.basic_builds]
        max_id = max(build_id_list) + 1
        self.db.session.commit()

        for _ in range(10):
            fake_id = random.randint(max_id, max_id * 10)
            href = "/api_2/builds/{}".format(fake_id)

            r = self.tc.get(href)
            assert r.status_code == 404

    def test_build_delete_ok(self, f_users, f_coprs,
                             f_mock_chroots, f_builds,f_users_api, ):

        self.db.session.commit()
        b_id = self.b1.id
        href = "/api_2/builds/{}".format(b_id)
        r = self.request_rest_api_with_auth(
            href,
            method="delete",
        )
        assert r.status_code == 204

        r2 = self.tc.get(href)
        assert r2.status_code == 404

    def test_build_delete_wrong_user(self, f_users, f_coprs,
                             f_mock_chroots, f_builds,f_users_api, ):

        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()
        b_id = self.b1.id
        href = "/api_2/builds/{}".format(b_id)
        r = self.request_rest_api_with_auth(
            href,
            method="delete",
            login=login, token=token,
        )
        assert r.status_code == 403

    def test_build_delete_in_progress(self, f_users, f_coprs,
                             f_mock_chroots, f_builds,f_users_api, ):

        login = self.u2.api_login
        token = self.u2.api_token
        self.db.session.commit()
        b_id = self.b3.id
        href = "/api_2/builds/{}".format(b_id)
        r = self.request_rest_api_with_auth(
            href,
            method="delete",
            login=login, token=token,
        )
        assert r.status_code == 400

    def test_build_put_wrong_user(
            self, f_users, f_coprs,
            f_mock_chroots, f_builds,f_users_api, ):

        login = self.u2.api_login
        token = self.u2.api_token

        for bc in self.b1_bc:
            bc.status = StatusEnum("pending")
            bc.ended_on = None

        self.b1.ended_on = None
        self.db.session.add_all(self.b1_bc)
        self.db.session.add(self.b1)

        self.db.session.commit()

        href = "/api_2/builds/{}".format(self.b1.id)
        build_dict = {
            "state": "canceled"
        }
        r = self.request_rest_api_with_auth(
            href,
            method="put",
            login=login, token=token,
            content=build_dict
        )
        assert r.status_code == 403

    def test_build_put_not_found(
            self, f_users, f_coprs,
            f_mock_chroots, f_builds,f_users_api, ):

        self.db.session.commit()
        href = "/api_2/builds/{}".format(10005000)
        build_dict = {
            "state": "canceled"
        }
        r = self.request_rest_api_with_auth(
            href,
            method="put",
            content=build_dict
        )
        assert r.status_code == 404

    def test_build_put_cancel(
            self, f_users, f_coprs,
            f_mock_chroots, f_builds,f_users_api, ):

        for bc in self.b1_bc:
            bc.status = StatusEnum("pending")
            bc.ended_on = None

        self.b1.ended_on = None
        self.db.session.add_all(self.b1_bc)
        self.db.session.add(self.b1)

        self.db.session.commit()

        href = "/api_2/builds/{}".format(self.b1.id)
        build_dict = {
            "state": "canceled"
        }
        r = self.request_rest_api_with_auth(
            href,
            method="put",
            content=build_dict
        )
        assert r.status_code == 201

        r2 = self.tc.get(r.headers["Location"])
        assert r2.status_code == 200
        obj = json.loads(r2.data.decode("utf-8"))
        assert obj["build"]["state"] == "canceled"

    def test_build_put_cancel_wrong_state(
            self, f_users, f_coprs,
            f_mock_chroots, f_builds,f_users_api, ):

        self.b1.ended_on = None
        old_state = self.b1.state
        self.db.session.add_all(self.b1_bc)
        self.db.session.add(self.b1)

        self.db.session.commit()

        href = "/api_2/builds/{}".format(self.b1.id)
        build_dict = {
            "state": "canceled"
        }
        r = self.request_rest_api_with_auth(
            href,
            method="put",
            content=build_dict
        )
        assert r.status_code == 400

        r2 = self.tc.get(href)
        assert r2.status_code == 200
        obj = json.loads(r2.data.decode("utf-8"))
        assert obj["build"]["state"] == old_state

