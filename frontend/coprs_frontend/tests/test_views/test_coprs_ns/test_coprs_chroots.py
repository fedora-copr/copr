import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator
from coprs.helpers import PermissionEnum
from coprs.models import CoprPermission


class TestCoprsChroots(CoprsTestCase):

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_edit_own_copr_chroot(self):
        """
        Test that a user can access and edit chroot settings of his project
        """
        self.db.session.add(self.c2)
        self.db.session.commit()

        url = "/coprs/{0}/edit_chroot/{1}/"\
            .format(self.c2.full_name, self.c2.mock_chroots[0].name)
        response = self.test_client.get(url, follow_redirects=True)
        assert response.status_code == 200

        url = "/coprs/{0}/update_chroot/{1}/"\
            .format(self.c2.full_name, self.c2.mock_chroots[0].name)
        data = {"buildroot_pkgs": "foo"}
        response = self.test_client.post(url, data=data, follow_redirects=True)
        assert response.status_code == 200

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_edit_someone_copr_chroot(self):
        """
        Test that a user can't access and edit chroot settings of someone else's
        project. While we are at it, check that having permission to build in
        the project doesn't change this fact.
        """
        perm = CoprPermission(
            copr=self.c1,
            user=self.u2,
            copr_builder=PermissionEnum("approved"),
            copr_admin=PermissionEnum("nothing")
        )
        self.db.session.add_all([self.c1, perm])
        self.db.session.commit()

        url = "/coprs/{0}/edit_chroot/{1}/"\
            .format(self.c1.full_name, self.c1.mock_chroots[0].name)
        response = self.test_client.get(url, follow_redirects=True)
        assert response.status_code == 403
        assert "You are not allowed to modify chroots in project"\
            in str(response.data)

        url = "/coprs/{0}/update_chroot/{1}/"\
            .format(self.c1.full_name, self.c1.mock_chroots[0].name)
        data = {"buildroot_pkgs": "foo"}
        response = self.test_client.post(url, data=data, follow_redirects=True)
        assert response.status_code == 403
        assert "You are not allowed to modify chroots in project"\
            in str(response.data)

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_edit_someone_copr_chroot_being_admin(self):
        """
        Test that as an admin of a project, user can access and edit its chroots
        """
        perm = CoprPermission(
            copr=self.c1,
            user=self.u2,
            copr_builder=PermissionEnum("nothing"),
            copr_admin=PermissionEnum("approved")
        )
        self.db.session.add_all([self.c1, perm])
        self.db.session.commit()

        url = "/coprs/{0}/edit_chroot/{1}/"\
            .format(self.c1.full_name, self.c1.mock_chroots[0].name)
        response = self.test_client.get(url, follow_redirects=True)
        assert response.status_code == 200

        url = "/coprs/{0}/update_chroot/{1}/"\
            .format(self.c1.full_name, self.c1.mock_chroots[0].name)
        data = {"buildroot_pkgs": "foo"}
        response = self.test_client.post(url, data=data, follow_redirects=True)
        assert response.status_code == 200
