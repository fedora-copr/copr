# coding: utf-8

import flask
import sqlalchemy

from .. import db
from .builds_logic import BuildsLogic
from coprs.exceptions import ObjectNotFound
from coprs.helpers import StatusEnum

from coprs.logic.users_logic import UsersLogic
from coprs.models import User
from .coprs_logic import CoprsLogic
from .. import helpers


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
            return CoprsLogic.get_by_group_id(
                group.id, copr_name, with_mock_chroots=True).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project @{}/{} does not exist."
                        .format(group_name, copr_name))

    @staticmethod
    def get_copr_safe(user_name, copr_name, **kwargs):
        try:
            return CoprsLogic.get(user_name, copr_name, **kwargs).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project {}/{} does not exist."
                        .format(user_name, copr_name))

    @staticmethod
    def get_build_safe(build_id):
        try:
            return BuildsLogic.get_by_id(build_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Build {} does not exist.".format(build_id))

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

    @staticmethod
    def get_active_groups_by_user(user_name):
        if "teams" in flask.session:
            names = flask.session["teams"]
            query = UsersLogic.get_groups_by_names_list(names)
            return query.filter(User.name == user_name)
        else:
            return []

    @staticmethod
    def get_queues_size():
        # todo: check if count works slowly

        waiting = BuildsLogic.get_build_task_queue().count()
        running = BuildsLogic.get_build_tasks(StatusEnum("running")).count()
        importing = BuildsLogic.get_build_tasks(helpers.StatusEnum("importing")).count()
        return dict(
            waiting=waiting,
            running=running,
            importing=importing
        )

