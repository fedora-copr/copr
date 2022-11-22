"""
Test the custom-directory (CoprDir) functionality
"""

import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprDir(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs", "f_builds",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    def test_custom_copr_dir(self):
        # De-synchronize the CoprDir.id, Copr.id and Package.id.
        self.web_ui.create_distgit_package("foocopr", "unused-package")
        self.api3.rebuild_package("foocopr:unused", "unused-package")

        self.web_ui.new_project("test", ["fedora-rawhide-i386"])

        self.web_ui.create_distgit_package("test", "copr-cli")
        self.web_ui.create_distgit_package("test", "copr-frontend")

        # should fail, we can not create sub-dir through "new package" request
        self.web_ui.create_distgit_package("test:asdf", "copr-cli",
                                           expected_status_code=404)

        out = self.api3.rebuild_package("test", "copr-cli")
        build_id_1 = out.json["id"]
        out = self.api3.rebuild_package("test:custom:subdir", "copr-frontend")
        build_id_2 = out.json["id"]
        self.backend.finish_build(build_id_1)
        self.backend.finish_build(build_id_2)

        params = {
            "ownername": "user1",
            "projectname": "test",
            "project_dirname": "test:custom:subdir",
        }
        res = self.tc.get("/api_3/monitor", query_string=params)
        assert len(res.json["packages"]) == 1
        assert res.json["packages"][0]["name"] == "copr-frontend"

        params = {
            "ownername": "user1",
            "projectname": "test",
        }
        res = self.tc.get("/api_3/monitor", query_string=params)
        assert len(res.json["packages"]) == 1
        assert res.json["packages"][0]["name"] == "copr-cli"

        # TODO: The rest of this test-case is actually testing a bad behavior.
        # The default "package/list" queries should be restricted to the main
        # directory, but they aren't.  They are "mixed-up", see the api3 route
        # /package/list, and how it is "dir agostic" while it still uses the
        # "get_packages_with_latest_builds_for_dir" method.
        params = {
            "ownername": "user1",
            "projectname": "test",
            "with_latest_succeeded_build": True,
        }
        res = self.tc.get("/api_3/package/list", query_string=params)

        # Two packages in this project
        packages = res.json["items"]
        assert len(packages) == 2
        latest_build = packages[0]["builds"]["latest_succeeded"]
        assert latest_build["project_dirname"] == "test"
        latest_build = packages[1]["builds"]["latest_succeeded"]
        assert latest_build["project_dirname"] == "test:custom:subdir"

        params = {
            "ownername": "user1",
            "projectname": "test",
            "with_latest_build": True,
        }
        res = self.tc.get("/api_3/package/list", query_string=params)

        packages = res.json["items"]
        assert len(packages) == 2
        latest_build = packages[0]["builds"]["latest"]
        assert latest_build["project_dirname"] == "test"
        latest_build = packages[1]["builds"]["latest"]
        assert latest_build["project_dirname"] == "test:custom:subdir"


    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs", "f_builds",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    def test_custom_dir_validation(self):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])
        self.web_ui.create_distgit_package("test", "copr-cli")
        # succeeds
        assert self.api3.rebuild_package("test:custom:subdir", "copr-cli").status_code == 200
        assert self.api3.rebuild_package("test:custom:123", "copr-cli").status_code  == 200
        assert self.api3.rebuild_package("test:custom:žluťoučký", "copr-cli").status_code  == 200
        assert self.api3.rebuild_package("test:custom:", "copr-cli").status_code == 400
        assert self.api3.rebuild_package("test:custom:.", "copr-cli").status_code == 400
        assert self.api3.rebuild_package("test:custom:@", "copr-cli").status_code == 400
        # This can be created by pagure-events.py and the custom webhook.
        assert self.api3.rebuild_package("test:pr:13", "copr-cli").status_code == 200
        assert self.api3.rebuild_package("test:pr:13a", "copr-cli").status_code == 400
        assert self.api3.rebuild_package("test:pr:13:2", "copr-cli").status_code == 400
