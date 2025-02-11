import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator
from coprs import models


class TestApiv3ProjectChroots(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_users_api",
                             "f_mock_chroots", "f_db")
    def test_edit_project_chroot_api(self):
        self.db.session.add(self.c1)

        chroot = self.c1.copr_chroots[0]
        route = "/api_3/project-chroot/edit/{0}/{1}".format(
            self.c1.full_name, chroot.name)
        check_route = "/api_3/project-chroot?ownername={owner}&projectname={project}&chrootname={chroot}"
        check_route = check_route.format(
            owner=chroot.copr.owner_name,
            project=chroot.copr.name,
            chroot=chroot.name)

        assert chroot.isolation == "unchanged"
        assert chroot.bootstrap is None
        assert chroot.buildroot_pkgs is None
        assert chroot.module_toggle is None

        data = {
            "isolation": "nspawn",
            "bootstrap": "off",
            "additional_packages": ["foo", "bar"],
            # list of additional modules
            "additional_modules": ["!aaa:devel", "blah:11"],
            "delete_comps": True,
        }
        response = self.api3.post(route, data)
        assert response.status_code == 200

        assert chroot.isolation == "nspawn"
        assert chroot.bootstrap == "off"
        assert chroot.buildroot_pkgs == "foo bar"
        assert chroot.module_toggle == "!aaa:devel, blah:11"

        data = {
            # Submit additional modules as comma-separated string
            "additional_modules": "module_b:11, !module_c:12",
        }

        response = self.api3.post(route, data)
        assert response.status_code == 200

        chroot = self.db.session.get(models.CoprChroot, chroot.id)
        assert chroot.isolation == "nspawn"
        assert chroot.bootstrap == "off"
        assert chroot.buildroot_pkgs == "foo bar"
        assert chroot.module_toggle == "module_b:11, !module_c:12"

        response = self.tc.get(check_route)
        assert response.status_code == 200
        assert response.json["additional_modules"] == [
            'module_b:11',
            '!module_c:12',
        ]

        # this shouldn't touch the additional_modules
        data = {"buildroot_pkgs": "foo"}
        response = self.api3.post(route, data)
        assert response.status_code == 200
        response = self.tc.get(check_route)
        assert response.status_code == 200
        assert response.json["additional_modules"] == [
            'module_b:11',
            '!module_c:12',
        ]

        # reset modules doesn't work this way
        data = {"additional_modules": []}
        response = self.api3.post(route, data)
        assert response.status_code == 200
        response = self.tc.get(check_route)
        assert response.status_code == 200
        assert response.json["additional_modules"] == [
            'module_b:11',
            '!module_c:12',
        ]

        # This is not a no-op.  This mimics the situation when user in web-UI
        # specifies an empty <input> field to reset the additional modules.
        data = {"additional_modules": ""}
        response = self.api3.post(route, data)
        assert response.status_code == 200
        response = self.tc.get(check_route)
        assert response.status_code == 200
        assert response.json["additional_modules"] == []
