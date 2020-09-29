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
            for url in ["/api_3/build-chroot/build-config/1/{0}".format(chroot),
                        "/backend/get-build-task/1-{}".format(chroot)]:
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
