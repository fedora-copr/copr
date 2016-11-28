# coding: utf-8

import time
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

        if copr.persistent:
            raise exceptions.InsufficientRightsException("This project is protected against deletion.")

        for build in builds_query:
            BuildsLogic.delete_build(flask.g.user, build, send_delete_action=False)

        CoprsLogic.delete_unsafe(flask.g.user, copr)

    @classmethod
    def fork_copr(cls, copr, user, dstname, dstgroup=None):
        forking = ProjectForking(user, dstgroup)
        created = (not bool(forking.get(copr, dstname)))
        fcopr = forking.fork_copr(copr, dstname)

        if fcopr.full_name == copr.full_name:
            raise exceptions.DuplicateException("Source project should not be same as destination")

        builds_map = {}
        for package in copr.packages:
            fpackage = forking.fork_package(package, fcopr)
            build = package.last_build(successful=True)
            if not build:
                continue

            fbuild = forking.fork_build(build, fcopr, fpackage)
            builds_map[fbuild.id] = build.result_dir_name

        ActionsLogic.send_fork_copr(copr, fcopr, builds_map)
        return fcopr, created

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
    def get_copr_by_owner_safe(owner_name, copr_name, **kwargs):
        if owner_name[0] == "@":
            return ComplexLogic.get_group_copr_safe(owner_name[1:], copr_name, **kwargs)
        return ComplexLogic.get_copr_safe(owner_name, copr_name, **kwargs)

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
    def get_package_by_id_safe(package_id):
        try:
            return PackagesLogic.get_by_id(package_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(
                message="Package {} does not exist.".format(package_id))

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

        waiting = BuildsLogic.get_build_task_queue(is_background=False).count()
        waiting_bg = BuildsLogic.get_build_task_queue(is_background=True).count()
        running = BuildsLogic.get_build_tasks(StatusEnum("running")).count()
        importing = BuildsLogic.get_build_tasks(helpers.StatusEnum("importing"), background=False).count()
        importing_bg = BuildsLogic.get_build_tasks(helpers.StatusEnum("importing"), background=True).count()
        return dict(
            waiting=waiting,
            running=running,
            importing=importing,
            waiting_bg=waiting_bg,
            importing_bg=importing_bg
        )


class ProjectForking(object):
    def __init__(self, user, group=None):
        self.user = user
        self.group = group

        if group and not user.can_build_in_group(group):
            raise exceptions.InsufficientRightsException(
                "Only members may create projects in the particular groups.")

    def get(self, copr, name):
        return CoprsLogic.get_by_group_id(self.group.id, name).first() if self.group \
            else CoprsLogic.filter_without_group_projects(CoprsLogic.get(flask.g.user.name, name)).first()

    def fork_copr(self, copr, name):
        fcopr = self.get(copr, name)
        if not fcopr:
            fcopr = self.create_object(models.Copr, copr, exclude=["id", "group_id", "created_on"])
            fcopr.forked_from_id = copr.id
            fcopr.user = self.user
            fcopr.user_id = self.user.id
            fcopr.created_on = int(time.time())
            if name:
                fcopr.name = name
            if self.group:
                fcopr.group = self.group
                fcopr.group_id = self.group.id

            for chroot in list(copr.copr_chroots):
                CoprChrootsLogic.create_chroot(self.user, fcopr, chroot.mock_chroot, chroot.buildroot_pkgs,
                                               chroot.repos, comps=chroot.comps, comps_name=chroot.comps_name)
            db.session.add(fcopr)
        return fcopr

    def fork_package(self, package, fcopr):
        fpackage = PackagesLogic.get(fcopr.id, package.name).first()
        if not fpackage:
            fpackage = self.create_object(models.Package, package, exclude=["id", "copr_id"])
            fpackage.copr = fcopr
            db.session.add(fpackage)
        return fpackage

    def fork_build(self, build, fcopr, fpackage):
        fbuild = self.create_object(models.Build, build, exclude=["id", "copr_id", "package_id"])
        fbuild.copr = fcopr
        fbuild.package = fpackage
        fbuild.build_chroots = [self.create_object(models.BuildChroot, c, exclude=["id", "build_id"]) for c in build.build_chroots]
        for chroot in fbuild.build_chroots:
            chroot.status = StatusEnum("forked")
        db.session.add(fbuild)
        db.session.commit()
        return fbuild

    def create_object(self, clazz, from_object, exclude=list()):
        arguments = {}
        for name, column in from_object.__mapper__.columns.items():
            if not name in exclude:
                arguments[name] = getattr(from_object, name)
        return clazz(**arguments)
