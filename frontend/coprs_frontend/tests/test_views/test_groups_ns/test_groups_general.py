# coding: utf-8
import pytest

from coprs import models

from coprs.logic.users_logic import UsersLogic

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestGroups(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_group_add(self, f_users, f_fas_groups, f_db):
        fas_name = f_fas_groups[0]
        alias = "alias_1"
        assert not UsersLogic.group_alias_exists(alias)
        r = self.test_client.post(
            "/groups/activate/{}".format(fas_name),
            data={"name": alias},
            follow_redirects=True
        )
        assert r.status_code == 200
        assert UsersLogic.group_alias_exists(alias)

    @TransactionDecorator("u1")
    def test_group_add_twice(self, f_users, f_fas_groups, f_db):
        fas_name = f_fas_groups[0]
        alias = "alias_1"
        assert not UsersLogic.group_alias_exists(alias)
        self.test_client.post(
            "/groups/activate/{}".format(fas_name),
            data={"name": alias},
            follow_redirects=True
        )
        assert UsersLogic.group_alias_exists(alias)
        assert len(models.Group.query.all()) == 1
        self.test_client.post(
            "/groups/activate/{}".format(fas_name),
            data={"name": alias},
            follow_redirects=True
        )
        assert len(models.Group.query.all()) == 1

    @TransactionDecorator("u1")
    def test_group_add_alias_with_space(self, f_users, f_fas_groups, f_db):
        fas_name = f_fas_groups[0]
        alias = "alias_1 foo bar"
        assert not UsersLogic.group_alias_exists(alias)
        r = self.test_client.post(
            "/groups/activate/{}".format(fas_name),
            data={"name": alias},
            follow_redirects=True
        )
        assert not UsersLogic.group_alias_exists(alias)

    @TransactionDecorator("u1")
    def test_group_add_not_in_fas_group(self, f_users, f_fas_groups, f_db):
        fas_name = f_fas_groups[3]
        alias = "alias_1"
        assert not UsersLogic.group_alias_exists(alias)
        r = self.test_client.post(
            "/groups/activate/{}".format(fas_name),
            data={"name": alias},
            follow_redirects=True
        )
        # assert r.status_code == 403
        assert not UsersLogic.group_alias_exists(alias)

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_groups", "f_db")
    def test_customize_group_profile_description(self):
        self.db.session.add_all([self.u1, self.g1])

        post = self.test_client.post(
            "/user/customize-profile/{}".format(self.g1.name),
            data={"profile_description": "Group **about** section"},
            follow_redirects=False,
        )

        assert post.status_code == 302
        group = self.db.session.merge(self.g1)
        assert group.profile_description == "Group **about** section"

        page = self.test_client.get("/groups/g/{}/coprs/".format(group.name)).data.decode("utf-8")
        assert "<strong>about</strong>" in page

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_groups", "f_db")
    def test_group_profile_description_forbidden(self):
        self.db.session.add_all([self.u2, self.g1])

        post = self.test_client.post(
            "/user/customize-profile/{}".format(self.g1.name),
            data={"profile_description": "forbidden"},
            follow_redirects=False,
        )

        assert post.status_code == 403
