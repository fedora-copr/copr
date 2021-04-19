"""
Test all kind of build request via v3 API
"""

import copy
import json

import pytest

from bs4 import BeautifulSoup
from copr_common.enums import BuildSourceEnum
from coprs.logic.builds_logic import BuildChrootResultsLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


# Items are
# =========
# 1. source type text
# 2. form data to be sent for build
# 3. expected "source_json" data to be set for the build
# 4. additionl "source_json" data expected to be set per-package

CASES = [(
    "distgit",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "mock",
    },
    {
        "clone_url": "git://prio.com/some/other/uri/mock/git",
    },
    {
        "distgit": "prioritized",
    },
), (
    "distgit",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "cpio",
        "distgit": "fedora",
    },
    {
        # no need to store "distgit" to source_json
        "clone_url": "https://src.fedoraproject.org/rpms/cpio"
    },
    {
        "distgit": "fedora",
    },
), (
    "distgit",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "tar",
        "committish": "f15",
    },
    {
        "committish": "f15",
        "clone_url": "git://prio.com/some/other/uri/tar/git",
    },
    {
        "distgit": "prioritized",

    },
), (
    "distgit",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "blah",
        "namespace": "@copr/copr",
        "distgit": "namespaced",
    },
    {
        "clone_url": "https://namespaced.org/some/other/uri/@copr/copr/blah/git",
    },
    {
        "distgit": "namespaced",
        "namespace": "@copr/copr",
    },
)]


BUILDOPTS = [
    {},
    {
        "chroots": ["fedora-17-x86_64"],
    },
    {"enable_net": True},
    {"enable_net": False},
]


# 1. description
# 2. form input
# 3. expected error contents
CASES_BAD = [(
    "no namespace specified",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "blah",
        "distgit": "namespaced",
    },
    ["Can not validate DistGit input", "specified"],
), (
    "non-existent distgit",
    {
        "ownername": "user2",
        "projectname": "foocopr",
        "package_name": "blah",
        "distgit": "nonexistent",
    },
    ["DistGit ID must be one of: prioritized, "],
)]


class TestAPIv3Builds(CoprsTestCase):

    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    @pytest.mark.parametrize("case", CASES)
    @pytest.mark.parametrize("buildopts", BUILDOPTS)
    def test_v3_builds(self, buildopts, case):
        source_type_text, data, source_json, _ = case
        form_data = copy.deepcopy(data)
        form_data.update(buildopts)

        endpoint = "/api_3/build/create/distgit"
        user = self.models.User.query.filter_by(username='user2').first()
        r = self.post_api3_with_auth(endpoint, form_data, user)
        assert r.status_code == 200
        build = self.models.Build.query.first()

        # We inherit enable_net config from project when not explicitly
        # set in build API call.
        assert build.enable_net == buildopts.get("enable_net", build.copr.build_enable_net)

        enabled_chroots = set(['fedora-17-x86_64', 'fedora-17-i386'])
        if not form_data.get("chroots"):
            assert build.chroots == []
        elif set(form_data['chroots']).issubset(enabled_chroots):
            real = {mch.name for mch in build.chroots}
            assert real == set(form_data["chroots"])
        else:
            assert build.chroots == []

        assert build.source_type == BuildSourceEnum(source_type_text)
        assert json.loads(build.source_json) == source_json

        timeout = buildopts.get("timeout")
        if timeout:
            assert build.timeout == timeout
        assert build.isolation == "unchanged"

    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    @pytest.mark.parametrize("case", CASES_BAD)
    def test_v3_build_failure(self, case):
        endpoint = "/api_3/build/create/distgit"
        user = self.models.User.query.filter_by(username='user2').first()
        # missing namespace
        _, form_data, errors = case
        response = self.post_api3_with_auth(endpoint, form_data, user)
        assert response.status_code == 400
        error_message = response.json['error']
        for error in errors:
            assert error in error_message

    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    def test_v3_get_build(self):
        data = {
            "ownername": "user2",
            "projectname": "foocopr",
            "package_name": "mock",
        }
        form_data = copy.deepcopy(data)
        form_data.update(dict(chroots=["fedora-17-x86_64"]))
        endpoint1 = "/api_3/build/create/distgit"
        user = self.models.User.query.filter_by(username='user2').first()
        self.post_api3_with_auth(endpoint1, form_data, user)
        build = self.models.Build.query.first()

        endpoint2 = f"/api_3/build/{build.id}"
        response1 = self.get_api3_with_auth(endpoint2, user)
        endpoint3 = f"/api_3/build/{build.id}/"
        response2 = self.get_api3_with_auth(endpoint3, user)

        assert response1.status_code == 200
        assert response1.json["ownername"] == "user2"
        assert response1.json["projectname"] == "foocopr"
        assert response2.status_code == 200
        assert response2.json["ownername"] == "user2"
        assert response2.json["projectname"] == "foocopr"

    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    @pytest.mark.parametrize("case", CASES)
    @pytest.mark.parametrize("exclude_chroots", [[], ["fedora-17-x86_64"]])
    def test_v3_builds_exclude_chroots(self, exclude_chroots, case):
        source_type_text, data, source_json, _ = case
        form_data = copy.deepcopy(data)
        form_data.update({"exclude_chroots": exclude_chroots})

        endpoint = "/api_3/build/create/distgit"
        user = self.models.User.query.filter_by(username="user2").first()
        r = self.post_api3_with_auth(endpoint, form_data, user)
        assert r.status_code == 200
        build = self.models.Build.query.first()

        if not exclude_chroots:
            assert not build.chroots
            return

        expected = {ch.name for ch in build.copr.active_chroots}
        expected -= set(exclude_chroots)
        assert {ch.name for ch in build.chroots} == expected

class TestWebUIBuilds(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_isolation_option_set(self):
        chroot = "fedora-rawhide-i386"
        project = "test"
        self.web_ui.new_project(project, [chroot], isolation="simple")
        route = "/coprs/{username}/{coprname}/edit/".format(
            username=self.transaction_username, coprname=project
        )

        def get_selected(html):
            soup = BeautifulSoup(html, "html.parser")
            return (soup.find("select", id="isolation")
                    .find("option", attrs={'selected': True}))

        resp = self.test_client.get(route)
        assert get_selected(resp.data)["value"] == "simple"


class TestAPIv3BuildsResults(CoprsTestCase):
    """
    Tests related to build results
    """

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    def test_build_built_packages(self):
        """
        Test the endpoint for getting built packages (NEVRA dicts) for a given
        build.
        """
        self.db.session.add(self.b1, self.b1_bc)
        nevra = {
            "name": "hello",
            "epoch": 0,
            "version": "2.8",
            "release": "1.fc33",
            "arch": "x86_64"
        }
        built_packages = {"packages": [nevra]}
        BuildChrootResultsLogic.create_from_dict(
            self.b1.build_chroots[0], built_packages)
        self.db.session.commit()

        endpoint = "/api_3/build/built-packages/{0}/".format(self.b1.id)
        result = self.tc.get(endpoint)
        assert result.is_json
        assert result.json["fedora-18-x86_64"] == built_packages
