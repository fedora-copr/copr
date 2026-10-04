"""
Tests for the per-project "Actions" tab
"""

import pytest
from copr_common.enums import BackendResultEnum
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprActions(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_actions_tab(self):
        """ The list of actions is rendered """
        self.db.session.add_all([self.c1, self.delete_action])
        url = f"/coprs/{self.c1.full_name}/actions/"
        response = self.test_client.get(url)
        assert response.status_code == 200
        page = response.data.decode("utf-8")
        assert "Project Actions" in page
        assert "cancel_build" in page
        assert "Possible action states" in page
        assert f"/action/{self.delete_action.id}/" in page

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_actions_tab_link_shown(self):
        """ The Actions tab is rendered on other project pages, too """
        self.db.session.add(self.c1)
        response = self.test_client.get(
            f"/coprs/{self.c1.full_name}/builds/")
        assert response.status_code == 200
        assert "/actions/" in response.data.decode("utf-8")

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_actions_tab_for_others(self):
        """ Actions are public, any user can see them """
        self.db.session.add(self.c1)
        url = f"/coprs/{self.c1.full_name}/actions/"
        response = self.test_client.get(url)
        assert response.status_code == 200
        assert "cancel_build" in response.data.decode("utf-8")

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_actions_tab_for_anonymous(self):
        """ Even anonymous visitors can see the actions """
        url = f"/coprs/{self.c1.full_name}/actions/"
        response = self.tc.get(url)
        assert response.status_code == 200
        assert "cancel_build" in response.data.decode("utf-8")

        url = (f"/coprs/{self.c1.full_name}"
               f"/action/{self.cancel_build_action.id}/")
        response = self.tc.get(url)
        assert response.status_code == 200
        assert "task_id&#34;: 123" in response.data.decode("utf-8")

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_action_detail(self):
        """ Action detail shows the status, message and the raw data """
        self.cancel_build_action.result = BackendResultEnum("failure")
        self.cancel_build_action.message = "Something went wrong"
        self.db.session.add_all([self.c1, self.cancel_build_action])
        self.db.session.commit()

        url = (f"/coprs/{self.c1.full_name}"
               f"/action/{self.cancel_build_action.id}/")
        response = self.test_client.get(url)
        assert response.status_code == 200
        page = response.data.decode("utf-8")
        assert "cancel_build" in page
        assert "Something went wrong" in page
        assert "failed" in page
        assert "Possible action states" in page
        # the 'data' column is pretty-printed (and html-escaped)
        assert "task_id&#34;: 123" in page

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_action_detail_from_other_project(self):
        """ Action ID from a different project is not found here """
        self.db.session.add_all([self.c2, self.delete_action])
        url = f"/coprs/{self.c2.full_name}/action/{self.delete_action.id}/"
        response = self.test_client.get(url, follow_redirects=True)
        assert response.status_code == 404

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_actions", "f_db")
    def test_action_detail_nonexisting(self):
        self.db.session.add(self.c1)
        url = f"/coprs/{self.c1.full_name}/action/123456/"
        response = self.test_client.get(url, follow_redirects=True)
        assert response.status_code == 404
