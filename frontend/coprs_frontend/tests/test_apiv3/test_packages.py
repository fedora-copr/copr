"""
Test all kind of build request via v3 API
"""

import copy
import json

import pytest

from copr_common.enums import BuildSourceEnum

from tests.coprs_test_case import CoprsTestCase
from tests.test_apiv3.test_builds import CASES


CHROOTS = [[], ["fedora-17-i386"]]


class TestAPIv3Packages(CoprsTestCase):

    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_other_distgit", "f_db")
    @pytest.mark.parametrize("case", CASES)
    @pytest.mark.parametrize("chroots", CHROOTS)
    def test_v3_packages(self, chroots, case):
        source_type_text, data, source_json, additional_data = case
        form_data = copy.deepcopy(data)
        expected_source_dict = copy.deepcopy(source_json)
        expected_source_dict.update(additional_data)
        pkg_name = form_data["package_name"]
        endpoint = "/api_3/package/add/{0}/{1}/{2}/{3}".format(
            "user2", "foocopr", pkg_name, source_type_text)

        user = self.models.User.query.filter_by(username='user2').first()
        r = self.post_api3_with_auth(endpoint, form_data, user)
        assert r.status_code == 200
        package = self.models.Package.query.first()
        assert package.name == pkg_name
        assert package.webhook_rebuild is False
        assert json.loads(package.source_json) == expected_source_dict

        # Try to edit the package.
        endpoint = "/api_3/package/edit/{0}/{1}/{2}/{3}".format(
            "user2", "foocopr", pkg_name, source_type_text)

        form_data["webhook_rebuild"] = True
        r = self.post_api3_with_auth(endpoint, form_data, user)
        assert r.status_code == 200

        package = self.models.Package.query.first()
        assert package.name == pkg_name
        assert json.loads(package.source_json) == expected_source_dict
        assert package.webhook_rebuild is True

        # Try to build the package.
        endpoint = "/api_3/package/build"
        rebuild_data = {
            "ownername": "user2",
            "projectname": form_data["projectname"],
            "package_name": form_data["package_name"],
        }
        self.post_api3_with_auth(endpoint, rebuild_data, user)
        build = self.models.Build.query.get(1)
        assert json.loads(build.source_json) == expected_source_dict
        assert build.source_type == BuildSourceEnum(source_type_text)

        def _assert_default_chroots(test_build):
            # We assign Package to Build as soon as possible, and at the same
            # time we allocate BuildChroots.
            assert {bch.name for bch in test_build.chroots} == {
                "fedora-17-x86_64",
                "fedora-17-i386",
            }

        _assert_default_chroots(build)
        rebuild_data["chroots"] = chroots
        self.post_api3_with_auth(endpoint, rebuild_data, user)
        build = self.models.Build.query.get(2)
        assert json.loads(build.source_json) == expected_source_dict
        if "fedora-18-x86_64" in chroots or chroots == []:
            _assert_default_chroots(build)
        else:
            assert [mch.name for mch in build.chroots] == ["fedora-17-i386"]
