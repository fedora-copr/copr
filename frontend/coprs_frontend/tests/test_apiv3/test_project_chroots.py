import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestApiv3ProjectChroots(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_users_api",
                             "f_mock_chroots", "f_db")
    def test_edit_project_chroot(self):
        self.db.session.add(self.c1)

        chroot = self.c1.copr_chroots[0]
        route = "/api_3/project-chroot/edit/{0}/{1}".format(
            self.c1.full_name, chroot.name)

        assert chroot.isolation == "unchanged"
        assert chroot.bootstrap is None
        assert chroot.buildroot_pkgs is None
        assert chroot.module_toggle is None

        data = {
            "isolation": "nspawn",
            "bootstrap": "off",
            "additional_packages": ["foo", "bar"],
            "additional_modules": ["!aaa:devel"],
            "delete_comps": True,
        }
        response = self.api3.post(route, data)
        assert response.status_code == 200

        assert chroot.isolation == "nspawn"
        assert chroot.bootstrap == "off"
        assert chroot.buildroot_pkgs == "foo bar"
        assert chroot.module_toggle == "!aaa:devel"
