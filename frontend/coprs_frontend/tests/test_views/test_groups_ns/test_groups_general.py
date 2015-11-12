# coding: utf-8
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
