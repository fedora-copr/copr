"""
Test variants of Mock bootstrap configuration in Copr project, chroot and a
concrete build.
"""

import json

import pytest

from coprs import models

from tests.coprs_test_case import (CoprsTestCase, TransactionDecorator)

# the None value means "unset"
VALID_BOOTSTRAP_CONFIG_CASES = [{
    "project": "image",
    "chroots": {
        "fedora-18-x86_64": ("custom_image", "fedora"),
        "fedora-17-i386": ("off", "fedora"),
        # the effect here is as if "custom_image" was set
        "fedora-17-x86_64": (None, "centos"),
        "fedora-rawhide-i386": ("on", None),
    },
    "build": None,
    "expected": {
        "fedora-18-x86_64": ("custom_image", "fedora"),
        "fedora-17-i386": ("off", None),
        "fedora-17-x86_64": ("custom_image", "centos"),
        "fedora-rawhide-i386": ("on", None),
    }
}, {
    "project": "off",
    "chroots": {
        "fedora-18-x86_64": ("custom_image", "fedora"),
        "fedora-rawhide-i386": ("on", None),
    },
    "build": "image",
    "expected": {
        "fedora-18-x86_64": ("image", None),
        "fedora-rawhide-i386": ("image", None),
    }
}, {
    "project": "on",
    "chroots": {
        "fedora-18-x86_64": (None, None),
        "fedora-rawhide-i386": ("image", None),
    },
    "build": "unchanged",
    "expected": {
        "fedora-18-x86_64": ("on", None),
        "fedora-rawhide-i386": ("image", None),
    }
}, {
    "project": None,
    "chroots": {
        "fedora-18-x86_64": ("custom_image", "fedora:18"),
        "fedora-rawhide-i386": (None, None),
    },
    "build": None,
    "expected": {
        "fedora-18-x86_64": ("custom_image", "fedora:18"),
        "fedora-rawhide-i386": (None, None),
    }
}, {
    "project": "default",
    "chroots": {
        "fedora-18-x86_64": (None, None),
        "fedora-rawhide-i386": ("on", None),
    },
    "build": "unchanged",
    "expected": {
        "fedora-18-x86_64": (None, None),
        "fedora-rawhide-i386": ("on", None),
    }
}]

VALID_ISOLATION_CONFIG_CASES = [{
    "project": None,
    "chroot": "fedora-rawhide-i386",
    "build": "default",
    "expected": "default",
}, {
    "project": "simple",
    "chroot": "fedora-rawhide-i386",
    "build": "default",
    "expected": "default",
}, {
    "project": "default",
    "chroot": "fedora-rawhide-i386",
    "build": "unchanged",
    "expected": "default",
}, {
    "project": "nspawn",
    "chroot": "fedora-rawhide-i386",
    "build": "simple",
    "expected": "simple",
}]

VALID_ISOLATION_CONFIG_CASES_CHROOT = [{
    "project": None,
    "chroot": "fedora-rawhide-i386",
    "build": "default",
    "chroot_isolation": "simple",
    "expected": "default",
}, {
    "project": "simple",
    "chroot": "fedora-rawhide-i386",
    "build": "unchanged",
    "chroot_isolation": "unchanged",
    "expected": "simple",
}, {
    "project": "default",
    "chroot": "fedora-rawhide-i386",
    "build": "unchanged",
    "chroot_isolation": "unchanged",
    "expected": "default",
}, {
    "project": "nspawn",
    "chroot": "fedora-rawhide-i386",
    "build": "unchanged",
    "chroot_isolation": "default",
    "expected": "default",
}]


class TestConfigOverrides(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    @pytest.mark.parametrize("case", VALID_BOOTSTRAP_CONFIG_CASES)
    def test_valid_configuration_cases(self, case, request_type):
        client = self.api3 if request_type == "api" else self.web_ui
        client.new_project("test-bootstrap", list(case["chroots"]),
                           bootstrap=case["project"])
        project = models.Copr.query.one()
        assert project.bootstrap == case["project"] or "default"
        for chroot in case["chroots"]:
            bootstrap, bootstrap_image = case["chroots"][chroot]
            kwargs = {}
            if bootstrap:
                kwargs["bootstrap"] = bootstrap
            if bootstrap_image:
                kwargs["bootstrap_image"] = bootstrap_image
            if not kwargs:
                continue
            client.edit_chroot("test-bootstrap", chroot, **kwargs)

        # create package so we can assign the build to that
        client.create_distgit_package("test-bootstrap", "tar")

        client.submit_url_build("test-bootstrap",
                                build_options={
                                    "chroots": list(case["chroots"]),
                                    "bootstrap": case["build"]})

        # Assign Package to Build, so we can query the (build/chroot) configs
        build = models.Build.query.one()
        build.package = models.Package.query.one()
        self.db.session.add(build)
        self.db.session.commit()

        for chroot in case["expected"]:
            urls = [
                "/api_3/build-chroot/build-config/1/{0}".format(chroot),
                "/api_3/build-chroot/build-config/1/{0}?build_id=1&chrootname={0}"\
                    .format(chroot),
                "/api_3/build-chroot/build-config?build_id=1&chrootname={0}"\
                    .format(chroot),
                "/backend/get-build-task/1-{}".format(chroot),
            ]
            for url in urls:
                bootstrap, bootstrap_image = case["expected"][chroot]
                response = self.test_client.get(url)
                assert response.status_code == 200
                result_dict = json.loads(response.data)

                if not bootstrap:
                    assert "bootstrap" not in result_dict
                if not bootstrap_image:
                    assert "bootstrap_image" not in result_dict

                assert result_dict.get("bootstrap") == bootstrap
                assert result_dict.get("bootstrap_image") == bootstrap_image

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    @pytest.mark.parametrize("case", VALID_ISOLATION_CONFIG_CASES)
    def test_isolation_override(self, case, request_type):
        """Override project configuration by build configuration."""
        client = self.api3 if request_type == "api" else self.web_ui
        client.new_project("test-isolation", [case["chroot"]],
                           isolation=case["project"])
        project = models.Copr.query.one()

        if case["project"]:
            assert project.isolation == case["project"]
        else:
            assert project.isolation == "default"

        self.create_build(case, client)

        isolation = case["expected"]
        response = self.test_client.get("/backend/get-build-task/1-{}".format(case["chroot"]))
        assert response.status_code == 200
        result_dict = json.loads(response.data)

        if not isolation:
            assert "isolation" not in result_dict
        assert result_dict.get("isolation") == isolation

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    @pytest.mark.parametrize("case", VALID_ISOLATION_CONFIG_CASES_CHROOT)
    def test_isolation_override_by_chroot(self, case, request_type):
        client = self.api3 if request_type == "api" else self.web_ui
        client.new_project("test-isolation", [case["chroot"]],
                           isolation=case["project"])
        project = models.Copr.query.one()

        if case["project"]:
            assert project.isolation == case["project"]
        else:
            assert project.isolation == "default"

        client.edit_chroot("test-isolation", case["chroot"], isolation=case["chroot_isolation"])
        self.create_build(case, client)

        isolation = case["expected"]
        response = self.test_client.get("/backend/get-build-task/1-{}".format(case["chroot"]))
        result_dict = json.loads(response.data)
        assert result_dict.get("isolation") == isolation

    def create_build(self, case, client):
        """Creates a new build
        :param case: Dictionary with cases.
        :param client: An instance of the API3Requests class or WebUIRequests class.
        """
        client.create_distgit_package("test-isolation", "tar")
        client.submit_url_build("test-isolation",
                                build_options={
                                    "chroots": [case["chroot"]],
                                    "isolation": case["build"]})
        build = models.Build.query.one()
        build.package = models.Package.query.one()
        self.db.session.add(build)
        self.db.session.commit()
