"""
Coverage for stuff related to CoprChroots
"""

from bs4 import BeautifulSoup
import pytest

from coprs import db
from coprs.models import Copr

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprChroots(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_edit_chroot_form(self):
        chroot = "fedora-rawhide-i386"
        project = "test"
        self.web_ui.new_project(project, [chroot],
                                bootstrap="on")
        route = "/coprs/{}/{}/edit_chroot/{}/".format(
            self.transaction_username, project, chroot,
        )
        def get_selected(html, element_id):
            soup = BeautifulSoup(html, "html.parser")
            return (soup.find("select", id=element_id)
                    .find("option", attrs={'selected': True}))

        resp = self.test_client.get(route)
        assert get_selected(resp.data, "bootstrap") is None

        self.web_ui.edit_chroot("test", chroot, bootstrap="on")

        resp = self.test_client.get(route)
        assert get_selected(resp.data, "bootstrap")["value"] == "on"
        assert get_selected(resp.data, "isolation")["value"] == "unchanged"

        self.web_ui.edit_chroot("test", chroot, isolation="simple")

        resp = self.test_client.get(route)
        assert get_selected(resp.data, "isolation")["value"] == "simple"

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_v3_edit_chroot(self):
        chroot = "fedora-rawhide-i386"
        project = "test"
        self.api3.new_project(project, [chroot])

        r = self.api3.edit_chroot(project, chroot, isolation="nspawn")
        assert r.status_code == 200

        copr = self.models.Copr.query.first()
        for chroot in copr.active_copr_chroots:
            assert chroot.isolation == "nspawn"

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_edit_chroot_permission(self):
        chroot = "fedora-rawhide-i386"
        project = "test"
        self.web_ui.new_project(project, [chroot],
                                bootstrap="on")
        copr = Copr.query.one()
        copr.user = self.u1
        db.session.commit()
        route = "/coprs/{}/{}/edit_chroot/{}/".format(
            self.u1.username, project, chroot,
        )
        resp = self.test_client.get(route)
        assert resp.status_code == 403

        self.web_ui.success_expected = False
        resp = self.web_ui.edit_chroot(project, chroot, bootstrap="off",
                                       owner=self.u1.username)
        assert resp.status_code == 403

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_edit_chroot_form_error(self):
        chroot = "fedora-rawhide-i386"
        project = "test"
        self.web_ui.new_project(project, [chroot],
                                bootstrap="on")
        self.web_ui.success_expected = False
        resp = self.web_ui.edit_chroot(project, chroot, bootstrap="invalid")
        assert resp.status_code == 200
        soup = BeautifulSoup(resp.data, "html.parser")
        div = soup.find("div", class_="alert alert-danger alert-dismissable")
        assert "Not a valid choice" in div.text
