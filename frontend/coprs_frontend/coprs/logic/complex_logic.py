# coding: utf-8

import flask
import sqlalchemy
from .builds_logic import BuildsLogic
from coprs.exceptions import ObjectNotFound
from coprs.logic.users_logic import UsersLogic
from .coprs_logic import CoprsLogic


class ComplexLogic(object):
    """
    Used for manipulation which affects multiply models
    """

    @classmethod
    def delete_copr(cls, copr):
        """
        Delete copr and all its builds.

        :param copr:
        :raises ActionInProgressException:
        :raises InsufficientRightsException:
        """
        builds_query = BuildsLogic.get_multiple_by_copr(copr=copr)

        for build in builds_query:
            BuildsLogic.delete_build(flask.g.user, build)

        CoprsLogic.delete_unsafe(flask.g.user, copr)

    @staticmethod
    def get_group_copr_safe(group_name, copr_name):
        group = ComplexLogic.get_group_by_name_safe(group_name)

        try:
            copr = CoprsLogic.get_by_group_id(
                group.id, copr_name, with_mock_chroots=True).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project {0} does not exist.".format(copr_name))

        return copr

    @staticmethod
    def get_group_by_name_safe(group_name):
        try:
            group = UsersLogic.get_group_by_alias(group_name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Group {} does not exist.".format(group_name))
        return group
    #
    # @staticmethod
    # def get_coprs_in_a_group(group_name):
    #     group = ComplexLogic.get_group_by_name_safe(group_name)
    #
    #
