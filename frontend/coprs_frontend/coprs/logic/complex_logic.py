# coding: utf-8

import flask
import sqlalchemy

from .. import db
from .builds_logic import BuildsLogic
from coprs import models
from coprs import exceptions
from coprs.exceptions import ObjectNotFound
from coprs.helpers import StatusEnum
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.actions_logic import ActionsLogic

from coprs.logic.users_logic import UsersLogic
from coprs.models import User, Copr
from .coprs_logic import CoprsLogic, CoprChrootsLogic
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

    @classmethod
    def fork_copr(cls, copr, user, dstname, dstgroup=None):
        if dstgroup and not user.can_build_in_group(dstgroup):
            raise exceptions.InsufficientRightsException(
                "Only members may create projects in the particular groups.")

        fcopr = CoprsLogic.get_by_group_id(dstgroup.id, dstname).first() if dstgroup \
            else CoprsLogic.filter_without_group_projects(CoprsLogic.get(flask.g.user.name, dstname)).first()

        if fcopr:
            raise exceptions.DuplicateException("You already have {}/{} project".format(user.name, copr.name))

        # @TODO Move outside and properly test it
        def create_object(clazz, from_object, exclude=list()):
            arguments = {}
            for name, column in from_object.__mapper__.columns.items():
                if not name in exclude:
                    arguments[name] = getattr(from_object, name)
            return clazz(**arguments)

        fcopr = create_object(models.Copr, copr, exclude=["id", "group_id"])
        fcopr.forked_from_id = copr.id
        fcopr.owner = user
        fcopr.owner_id = user.id
        if dstname:
            fcopr.name = dstname
        if dstgroup:
            fcopr.group = dstgroup
            fcopr.group_id = dstgroup.id

        for chroot in list(copr.copr_chroots):
            CoprChrootsLogic.create_chroot(user, fcopr, chroot.mock_chroot, chroot.buildroot_pkgs,
                                           comps=chroot.comps, comps_name=chroot.comps_name)

        builds_map = {}
        for package in copr.packages:
            fpackage = create_object(models.Package, package, exclude=["id", "copr_id"])
            fpackage.copr = fcopr
            db.session.add(fpackage)

            build = package.last_build()
            if not build:
                continue

            fbuild = create_object(models.Build, build, exclude=["id", "copr_id", "package_id"])
            fbuild.copr = fcopr
            fbuild.package = fpackage
            fbuild.build_chroots = [create_object(models.BuildChroot, c, exclude=["id"]) for c in build.build_chroots]
            db.session.add(fbuild)
            builds_map[fbuild.id] = build.id

        ActionsLogic.send_fork_copr(copr, fcopr, builds_map)
        db.session.add(fcopr)
        return fcopr

    @staticmethod
    def get_group_copr_safe(group_name, copr_name, **kwargs):
        group = ComplexLogic.get_group_by_name_safe(group_name)

        try:
            return CoprsLogic.get_by_group_id(
                group.id, copr_name, **kwargs).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project @{}/{} does not exist."
                        .format(group_name, copr_name))

    @staticmethod
    def get_copr_safe(user_name, copr_name, **kwargs):
        """ Get one project

        This always return personal project. For group projects see get_group_copr_safe().
        """
        try:
            return CoprsLogic.get(user_name, copr_name, **kwargs).filter(Copr.group_id.is_(None)).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project {}/{} does not exist."
                        .format(user_name, copr_name))

    @staticmethod
    def get_copr_by_id_safe(copr_id):
        try:
            return CoprsLogic.get_by_id(copr_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Project with id {} does not exist."
                        .format(copr_id))

    @staticmethod
    def get_build_safe(build_id):
        try:
            return BuildsLogic.get_by_id(build_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Build {} does not exist.".format(build_id))

    @staticmethod
    def get_package_safe(copr, package_name):
        try:
            return PackagesLogic.get(copr.id, package_name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Package {} in the copr {} does not exist."
                .format(package_name, copr))

    @staticmethod
    def get_group_by_name_safe(group_name):
        try:
            group = UsersLogic.get_group_by_alias(group_name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Group {} does not exist.".format(group_name))
        return group

    @staticmethod
    def get_copr_chroot_safe(copr, chroot_name):
        try:
            chroot = CoprChrootsLogic.get_by_name_safe(copr, chroot_name)
        except (ValueError, KeyError, RuntimeError) as e:
            raise ObjectNotFound(message=str(e))

        if not chroot:
            raise ObjectNotFound(
                message="Chroot name {} does not exist.".format(chroot_name))

        return chroot
    #
    # @staticmethod
    # def get_coprs_in_a_group(group_name):
    #     group = ComplexLogic.get_group_by_name_safe(group_name)
    #
    #

    @staticmethod
    def get_active_groups_by_user(user_name):
        names = flask.g.user.user_groups
        if names:
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

