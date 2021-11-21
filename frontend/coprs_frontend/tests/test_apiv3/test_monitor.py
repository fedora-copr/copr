"""
Test /api_3/monitor
"""

import pytest

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestAPIv3Monitor(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    @pytest.mark.parametrize("case", [
        {"project_dirname": "nonexistent"},  # non-existing dir
        {"project_dirname": "foocopr"},      # main dir
        {"additional_fields[]": ["url_build_log", "url_backend_log"]},
        {"additional_fields[]": ["wrongarg1", "wrongarg2"]},
    ])
    def test_v3_monitor(self, case):
        params = {
            "ownername": "user1",
            "projectname": "foocopr",
        }
        params.update(case)
        result = self.tc.get("/api_3/monitor", query_string=params)
        if case.get("project_dirname") == "nonexistent":
            assert result.status_code == 404
            assert "'nonexistent' doesn't exist in 'user1/" in result.json["error"]
            return

        if case.get("additional_fields[]") and \
                    "wrongarg1" in case["additional_fields[]"]:
            assert result.status_code == 400
            assert result.json["error"] == \
                   "Wrong additional_fields argument(s): wrongarg1, wrongarg2"
            return

        self.api3.create_distgit_package("foocopr", "cpio")
        self.api3.rebuild_package("foocopr", "cpio")
        self.backend.finish_build(5)

        assert self.tc.get("/api_3/monitor", query_string=params).json \
               == {
            "message": "Project monitor request successful",
            "output": "ok",
            "packages": [{
                "name": "cpio",
                "chroots": {
                    "fedora-18-x86_64": {
                            "build_id": 5,
                            "state": "succeeded",
                            "status": 1,
                            "pkg_version": "1",
                    } | ({
                            "url_backend_log": (
                                "http://copr-be-dev.cloud.fedoraproject.org/"
                                "results/user1/foocopr/fedora-18-x86_64/xyz/"
                                "backend.log.gz"),
                            "url_build_log": (
                                "http://copr-be-dev.cloud.fedoraproject.org/"
                                "results/user1/foocopr/fedora-18-x86_64/xyz/"
                                "builder-live.log.gz"),
                    } if "additional_fields[]" in case else {})
                },
            }, {
                "name": "hello-world",
                "chroots": {
                    "fedora-18-x86_64": {
                        "build_id": 2,
                        "state": "waiting",
                        "status": 9,
                        "pkg_version": None,
                    } | ({
                        "url_backend_log": None,
                        "url_build_log": None,
                    } if "additional_fields[]" in case else {})
                },
            }]
        }

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_v3_monitor_empty_project(self):
        self.web_ui.new_project(
            "test",
            ["fedora-rawhide-i386", "fedora-18-x86_64"])
        self.web_ui.create_distgit_package("test", "tar")
        result = self.tc.get("/api_3/monitor", query_string={
            "ownername": "user1",
            "projectname": "test",
        })
        assert result.json == {
            "message": "Project monitor request successful",
            "output": "ok",
            "packages": [],
        }


    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_v3_monitor_multi_chroot(self):
        self.web_ui.new_project(
            "test",
            ["fedora-rawhide-i386", "fedora-18-x86_64"])
        self.web_ui.create_distgit_package("test", "tar")
        self.api3.rebuild_package("test", "tar")
        self.backend.finish_build(1, package_name="tar")

        assert self.tc.get("/api_3/monitor", query_string={
            "ownername": "user1",
            "projectname": "test",
        }).json == {
            "message": "Project monitor request successful",
            "output": "ok",
            "packages": [{
                "name": "tar",
                "chroots": {
                    "fedora-18-x86_64": {
                        "build_id": 1,
                        "state": "succeeded",
                        "status": 1,
                        "pkg_version": "1",
                    },
                    "fedora-rawhide-i386": {
                        "build_id": 1,
                        "state": "succeeded",
                        "status": 1,
                        "pkg_version": "1",
                    },
                },
            }]
        }

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_v3_monitor_source_build(self):
        self.web_ui.new_project(
            "test",
            ["fedora-rawhide-i386", "fedora-18-x86_64"])
        self.web_ui.create_distgit_package("test", "tar")
        self.api3.rebuild_package("test", "tar")

        def _fixup_result(result_dict, update=None):
            for package in result_dict["packages"]:
                for _, chroot in package["chroots"].items():
                    if update:
                        chroot.update(update)

        result = self.tc.get("/api_3/monitor", query_string={
            "ownername": "user1",
            "projectname": "test",
            "additional_fields[]": ["url_build_log"],
        }).json
        _fixup_result(result)

        expected_result = {
            'message': 'Project monitor request successful',
            'output': 'ok',
            'packages': [{
                "name": "tar",
                'chroots': {
                    'fedora-rawhide-i386': {
                        'build_id': 1,
                        'state': 'waiting',
                        'status': 9,
                        # we don't have build log here
                        'url_build_log': None,
                        'pkg_version': None,
                    },
                    'fedora-18-x86_64': {
                        'build_id': 1,
                        'state': 'waiting',
                        'status': 9,
                        # we don't have build log here
                        'url_build_log': None,
                        'pkg_version': None,
                    },
                },
            }]
        }
        assert result == expected_result

        # finish with source failure
        self.backend.fail_source_build(1)
        result = self.tc.get("/api_3/monitor", query_string={
            "ownername": "user1",
            "projectname": "test",
            "additional_fields[]": ["url_build_log"],
        }).json
        _fixup_result(result)

        # We expect that the result is failed!
        _fixup_result(expected_result, update={
            "status": 0,
            "state": "failed",
        })
        assert result == expected_result
