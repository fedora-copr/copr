# coding: utf-8

# This module is slightly over the limit, splitting it is a separate story
# pylint: disable=too-many-lines

import os
import datetime
import time
import fnmatch
import flask
import sqlalchemy

from copr_common.enums import StatusEnum, StorageEnum
from coprs import app
from coprs import db
from coprs import helpers
from coprs import models
from coprs import exceptions
from coprs import cache
from coprs.constants import DEFAULT_COPR_REPO_PRIORITY
from coprs.exceptions import ObjectNotFound
from coprs.repos import (
    copr_repo_fullname,
    parse_repo_params,
    generate_repo_name,
    pre_process_repo_url,
)
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.batches_logic import BatchesLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.stat_logic import CounterStatLogic

from coprs.logic.users_logic import UsersLogic
from coprs.models import User, Copr, AutomationUser
from coprs.logic.coprs_logic import (CoprsLogic, CoprDirsLogic, CoprChrootsLogic,
                                     PinnedCoprsLogic, MockChrootsLogic)
from coprs.helpers import batched


@sqlalchemy.event.listens_for(models.Copr.deleted, "set")
def unpin_projects_on_delete(copr, deleted, oldvalue, event):
    if not deleted:
        return
    PinnedCoprsLogic.delete_by_copr(copr)


class ComplexLogic(object):
    """
    Used for manipulation which affects multiply models
    """
    # pylint: disable=too-many-public-methods

    @classmethod
    def get_transitive_runtime_dependencies(cls, copr):
        """Get a list of runtime dependencies (build transitively from
        dependencies' dependencies). Returns three lists, one with Copr
        dependencies, one with list of non-existing Copr dependencies
        and one with URLs to external dependencies.

        :type copr: models.Copr
        :rtype: List[models.Copr], List[str], List[str]
        """

        if not copr:
            return [], [], []

        wlist = helpers.WorkList([copr])
        internal_deps = set()
        non_existing = set()
        external_deps = set()

        while not wlist.empty:
            analyzed_copr = wlist.pop()

            for dep in analyzed_copr.runtime_deps:
                try:
                    copr_dep = cls.get_copr_by_repo(dep)
                except exceptions.ObjectNotFound:
                    non_existing.add(dep)
                    continue

                if not copr_dep:
                    external_deps.add(dep)
                    continue
                if copr == copr_dep:
                    continue
                # check transitive dependencies
                internal_deps.add(copr_dep)
                wlist.schedule(copr_dep)

        return list(internal_deps), list(external_deps), list(non_existing)

    @classmethod
    def delete_copr(cls, copr, admin_action=False):
        """
        Delete copr and all its builds.

        :param copr:
        :param admin_action: set to True to bypass permission check
        :raises ActionInProgressException:
        :raises InsufficientRightsException:
        """

        if admin_action:
            user = AutomationUser(name="automation user")
        else:
            user = flask.g.user

        builds = [x.id for x in BuildsLogic.get_multiple_by_copr(copr=copr)]

        if copr.persistent:
            raise exceptions.InsufficientRightsException("This project is protected against deletion.")

        for chunk in batched(builds, 1000):
            # Don't send delete action for each build, rather send an action to delete
            # a whole project as a part of CoprsLogic.delete_unsafe() method.
            BuildsLogic.delete_builds(user, chunk, send_delete_action=False)

        CoprsLogic.delete_unsafe(user, copr)


    @classmethod
    def delete_expired_projects(cls, limit=None):
        query = (
            models.Copr.query
            .filter(models.Copr.delete_after.isnot(None))
            .filter(models.Copr.delete_after < datetime.datetime.now())
            .filter(models.Copr.deleted.isnot(True))
            .limit(limit)
        )
        deleted = 0
        for copr in query.all():
            print("deleting project '{}'".format(copr.full_name))
            try:
                cls.delete_copr(copr, admin_action=True)
                deleted += 1
            except exceptions.BadRequest as e:
                # Ideally, we would like to catch only ActionInProgressException
                # but the BuildsLogic.delete_builds method generalizes the
                # exceptions and raises BadRequest.
                if "still running" not in str(e):
                    raise e
                print(e)
                print("project {} postponed".format(copr.full_name))
        return deleted


    @classmethod
    def fork_copr(cls, src_copr, forking_user, dst_name, dst_group=None,
                  all_builds=False, dst_user=None):
        """
        Fork src_copr into the dst_name project in the dst_user (or
        dst_group) namespace.  The destination project doesn't have to
        exist;  if it does, it is only filled with the packages and builds
        missing there.

        Returns a (dst_copr, created) tuple where 'created' says which of
        the two happened - the callers report those cases differently
        ("project forked" vs. "packages updated").
        """
        # we walk through the whole project here, packages, builds and their
        # chroots;  splitting this into pieces wouldn't help anyone
        # pylint: disable=too-many-locals
        cls.raise_if_too_large_to_fork(forking_user, src_copr)
        forking = ProjectForking(forking_user, dst_name, dst_group, dst_user)

        # Ask *before* forking.  Afterwards the destination project exists
        # either way, and we could no longer tell whether we have just
        # created it, or whether it had been there before.
        created = not forking.destination_exists()

        dst_copr = forking.fork_copr(src_copr)

        if dst_copr.full_name == src_copr.full_name:
            raise exceptions.DuplicateException("Source project should not be same as destination")

        builds_map = {}
        for src_chroot in src_copr.active_chroots:
            builds_map[src_chroot.name] = {}

        srpm_builds_src = []
        srpm_builds_dst = []

        for src_package in src_copr.packages:
            dst_package = forking.fork_package(src_package, dst_copr)

            builds = PackagesLogic.successful_build_chroots(src_package, all_builds=all_builds)
            if not builds:
                continue

            # We need to guarantee the build order as it is in the source
            # repository, because otherwise the metadata (NEVRA) in the target
            # Package won't be accurate (the last forked build actually
            # overwrites the NEVRA in Package).
            #
            # Also, the "max builds" feature doesn't address NEVRA at all, but
            # rather retains the latest BUILD IDs... so it would delete builds
            # in the wrong order.
            for src_build, src_chroots in sorted(builds.items(), key=lambda item: item[0].id):
                dst_build = forking.fork_build(src_build, dst_copr,
                                               dst_package, src_chroots)

                if src_build.result_dir:
                    srpm_builds_src.append(src_build.result_dir)
                    srpm_builds_dst.append(dst_build.result_dir)

                for src_chroot, dst_chroot in zip(src_chroots, dst_build.build_chroots):
                    if not src_chroot.result_dir:
                        continue
                    if src_chroot.name not in builds_map:
                        builds_map[src_chroot.name] = {src_chroot.result_dir: dst_chroot.result_dir}
                    else:
                        builds_map[src_chroot.name][src_chroot.result_dir] = dst_chroot.result_dir

        builds_map['srpm-builds'] = dict(zip(srpm_builds_src, srpm_builds_dst))

        db.session.commit()
        ActionsLogic.send_fork_copr(src_copr, dst_copr, builds_map)
        return dst_copr, created

    @staticmethod
    def get_group_copr(group_name, copr_name, **kwargs):
        """
        Get group Copr by group and copr name.

        Returns:
            Copr model

        Raises:
            ObjectNotFound to API if nothing is found in database
        """
        group = ComplexLogic.get_group_by_name(group_name)
        try:
            return CoprsLogic.get_by_group_id(
                group.id, copr_name, **kwargs).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Project @{}/{} does not exist.".format(
                    group_name, copr_name
                )
            ) from exc

    @staticmethod
    def get_copr(user_name, copr_name, **kwargs):
        """ Get one project.

        This always return personal project. For group projects see get_group_copr().
        """
        try:
            return CoprsLogic.get(user_name, copr_name, **kwargs).filter(Copr.group_id.is_(None)).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Project {}/{} does not exist.".format(
                    user_name, copr_name
                )
            ) from exc

    @staticmethod
    def get_copr_by_owner(owner_name, copr_name, **kwargs):
        """
        Get Copr by owner name and copr name.

        Returns:
            Copr model

        Raises:
            ObjectNotFound to API if nothing is found in database
        """
        if owner_name[0] == "@":
            return ComplexLogic.get_group_copr(owner_name[1:], copr_name, **kwargs)
        return ComplexLogic.get_copr(owner_name, copr_name, **kwargs)

    @staticmethod
    def get_copr_by_repo(repo_url):
        """
        Safely get copr repo by repo url.

        Args:
            repo_url: str

        Returns:
            Copr repo or None in case of invalid url format or different url
             scheme than copr.

        Raises:
            ObjectNotFound to the API if no such Copr (group) result was found
             in database.
        """
        copr_repo = copr_repo_fullname(repo_url)
        if not copr_repo:
            return None
        try:
            owner, copr = copr_repo.split("/")
        except ValueError:
            # invalid format, e.g. multiple slashes in copr_repo
            return None
        return ComplexLogic.get_copr_by_owner(owner, copr)

    @staticmethod
    def get_copr_dir(ownername, copr_dirname):
        """
        Get CoprDir by owner name and dir name.

        Returns:
            CoprDir model

        Raises:
            ObjectNotFound to the API if no result was found in database.
        """
        try:
            return CoprDirsLogic.get_by_ownername(ownername, copr_dirname).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="copr dir {}/{} does not exist.".format(
                    ownername, copr_dirname
                )
            ) from exc

    @staticmethod
    def get_copr_by_id(copr_id):
        """
        Get Copr by its ID.

        Returns:
            Copr model

        Raises:
            ObjectNotFound to the API if no such project with ID exists.
        """
        try:
            return CoprsLogic.get_by_id(copr_id).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Project with id {} does not exist.".format(copr_id)
            ) from exc

    @staticmethod
    def get_build(build_id):
        """
        Get Build by its ID.

        Returns:
            Build model

        Raises:
            ObjectNotFound to the API if no such build with ID exists.
        """
        try:
            return BuildsLogic.get_by_id(build_id).one()
        except (sqlalchemy.orm.exc.NoResultFound, sqlalchemy.exc.DataError) as exc:
            raise ObjectNotFound(
                message="Build {} does not exist.".format(build_id)
            ) from exc

    @staticmethod
    def get_build_chroot(build_id, chrootname):
        """
        Get a BuildChroot instance based on build ID and name of the chroot.

        Returns:
            BuildChroot model

        Raises:
            If there is no such chroot, `ObjectNotFound` execption is raised.
        """
        build = ComplexLogic.get_build(build_id)
        try:
            return build.chroots_dict_by_name[chrootname]
        except KeyError as exc:
            msg = "Build {} was not submitted to {} chroot.".format(build_id, chrootname)
            if not MockChrootsLogic.get_from_name(chrootname).one_or_none():
                msg = "Chroot {} does not exist".format(chrootname)
            raise ObjectNotFound(message=msg) from exc

    @staticmethod
    def get_package_by_id(package_id):
        """
        Get Package instance based on its ID.

        Returns:
            Package model

        Raises:
            ObjectNotFound to the API if no such package with ID exists.
        """
        try:
            return PackagesLogic.get_by_id(package_id).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Package {} does not exist.".format(package_id)
            ) from exc

    @staticmethod
    def get_package(copr, package_name):
        """
        Get Package instance based on Copr instance and package name.

        Returns:
            Package model

        Raises:
            ObjectNotFound to the API if no such package with given name
             exists.
        """
        try:
            return PackagesLogic.get(copr.id, package_name).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Package {} in the copr {} does not exist.".format(
                    package_name, copr
                )
            ) from exc

    @staticmethod
    def get_group_by_name(group_name):
        """
        Get Group instance based on a given name.

        Returns:
            Group model

        Raises:
            ObjectNotFound for the API if no such group name exists.
        """
        try:
            group = UsersLogic.get_group_by_alias(group_name).one()
        except sqlalchemy.orm.exc.NoResultFound as exc:
            raise ObjectNotFound(
                message="Group {} does not exist.".format(group_name)
            ) from exc
        return group

    @staticmethod
    def get_copr_chroot(copr, chroot_name):
        """
        Get CoprChroot by Copr model and chroot name.

        Returns:
            CoprChroot model

        Raises:
            ObjectNotFound for the API if no such chroot name exists in Copr.
        """
        try:
            chroot = CoprChrootsLogic.get_by_name_or_none(copr, chroot_name)
        except (ValueError, KeyError, RuntimeError) as e:
            raise ObjectNotFound(message=str(e)) from e

        if not chroot:
            raise ObjectNotFound(
                message="Chroot name {0} does not exist in Copr {1}."
                .format(chroot_name, copr.full_name)
            )

        return chroot

    @staticmethod
    def get_active_groups_by_user(user_name):
        names = flask.g.user.user_groups
        if names:
            query = UsersLogic.get_groups_by_names_list(names)
            return query.filter(User.name == user_name)
        else:
            return []

    @classmethod
    @cache.memoize(timeout=60)
    def get_queue_sizes_cached(cls):
        """
        The `get_queue_sizes` is IMHO reasonably fast but it is still a major
        slowdown of rendering the homepage. It is safe to use a cached variant
        there.
        """
        return cls.get_queue_sizes()

    @staticmethod
    def get_queue_sizes():
        importing = BuildsLogic.get_build_importing_queue(background=False).count()
        pending = BuildsLogic.get_pending_build_tasks(background=False).count() +\
            BuildsLogic.get_pending_srpm_build_tasks(background=False).count()
        running = BuildsLogic.get_build_tasks(StatusEnum("running")).count() +\
            BuildsLogic.get_srpm_build_tasks(StatusEnum("running")).count()
        starting = BuildsLogic.get_build_tasks(StatusEnum("starting")).count() +\
            BuildsLogic.get_srpm_build_tasks(StatusEnum("starting")).count()

        return dict(
            importing=importing,
            pending=pending,
            running=running,
            starting=starting,
            batches=BatchesLogic.pending_batch_count_cached(),
        )

    @classmethod
    def get_coprs_permissible_by_user(cls, user):
        coprs = CoprsLogic.filter_without_group_projects(
                    CoprsLogic.get_multiple_owned_by_username(
                        user.username, include_unlisted_on_hp=False)).all()

        for group in user.user_groups:
            coprs.extend(CoprsLogic.get_multiple_by_group_id(group.id).all())

        coprs += [perm.copr for perm in user.copr_permissions if
                  perm.get_permission("admin") == helpers.PermissionEnum("approved") or
                  perm.get_permission("builder") == helpers.PermissionEnum("approved")]

        return set(coprs)

    @classmethod
    def get_coprs_pinnable_by_owner(cls, owner):
        if isinstance(owner, models.Group):
            UsersLogic.raise_if_not_in_group(flask.g.user, owner)
            coprs = CoprsLogic.get_multiple_by_group_id(owner.id)
            coprs = coprs.filter(models.Copr.unlisted_on_hp.is_(False)).all()
        else:
            coprs = ComplexLogic.get_coprs_permissible_by_user(owner)
        return sorted(coprs, key=lambda copr: copr.full_name)

    @classmethod
    def raise_if_too_large_to_fork(cls, forking_user, src_copr):
        """
        Everybody may fork from any project, we just don't want anyone to
        duplicate the really huge ones (FORK_PACKAGES_LIMIT).  Raise
        CoprHttpException if src_copr is over the limit, return None
        otherwise.  Copr maintainers are not limited.
        """
        limit = app.config["FORK_PACKAGES_LIMIT"]
        packages_count = PackagesLogic.get_all(src_copr.id).count()
        if packages_count > limit and not forking_user.admin:
            msg = ("This project is too large to be forked, it has {0} "
                   "packages. Forking this such projects is restricted because "
                   "it could cause unexpected performance or storage issues. "
                   "If you would like to proceed with this action, "
                   "please contact Copr maintainers.".format(packages_count))
            raise exceptions.CoprHttpException(msg)

    @classmethod
    def fork_destination(cls, forking_user, dst_ownername):
        """
        Translate the "ownername" of a fork destination into a
        (dst_user, dst_group) tuple.  No permission checks are done here,
        that's a job for ProjectForking.raise_if_cant_fork_into().
        """
        if dst_ownername.startswith("@"):
            return forking_user, cls.get_group_by_name(dst_ownername[1:])

        if dst_ownername == forking_user.name:
            return forking_user, None

        dst_user = UsersLogic.get(dst_ownername).first()
        if not dst_user:
            raise ObjectNotFound("No such user `{0}'".format(dst_ownername))
        return dst_user, None

    @staticmethod
    def get_fork_destination_copr(dst_name, dst_user, dst_group=None):
        """
        Get the already existing project a fork would be merged into, or None
        if there's no such project (yet).
        """
        if dst_group:
            return CoprsLogic.get_by_group_id(dst_group.id, dst_name).first()
        return CoprsLogic.filter_without_group_projects(
            CoprsLogic.get(dst_user.name, dst_name)).first()


class ProjectForking(object):
    """
    Fork into the destination project given by (dst_user|dst_group)/dst_name.
    That destination is fixed for the whole lifetime of the object, and
    fork_copr() either finds it, or creates it.

    The fork_package()/fork_build() methods take the destination project as
    an argument instead (and dst_name is optional for them), so that they
    can be used separately, without any parent fork_copr() call.
    """
    def __init__(self, forking_user, dst_name=None, dst_group=None,
                 dst_user=None):
        # The user who performs the fork, it is their permissions that we
        # check against the destination project/namespace.
        self.forking_user = forking_user
        self.dst_name = dst_name
        self.dst_group = dst_group
        # The destination namespace owner;  it is the forking user themselves
        # unless we fork into a project owned by somebody else.
        self.dst_user = dst_user or forking_user

    def get_destination(self):
        """
        The project we are going to fork into, None if it doesn't exist yet.
        """
        return ComplexLogic.get_fork_destination_copr(self.dst_name,
                                                      self.dst_user,
                                                      self.dst_group)

    def destination_exists(self):
        """
        True when the destination project is already there and we are only
        going to fill it with the missing packages/builds.
        """
        return bool(self.get_destination())

    def raise_if_cant_fork_into(self, existing_copr):
        """
        Raise InsufficientRightsException if self.forking_user is not allowed
        to fork into the destination project (existing_copr is None when
        there's no such project yet).
        """
        if existing_copr:
            # Forking into an existing project only modifies that project, so
            # the permission to administer it is what we require here.  It
            # doesn't matter whose namespace it lives in.  Note that being
            # just a builder there is not enough.
            if not self.forking_user.can_edit(existing_copr):
                raise exceptions.InsufficientRightsException(
                    "You don't have permissions to administer the {0} project."
                    .format(existing_copr.full_name))

        elif self.dst_group:
            # A new project is about to be created in the group, so the same
            # check as when creating a project from scratch applies.
            UsersLogic.raise_if_not_in_group(self.forking_user, self.dst_group)

        elif self.dst_user != self.forking_user and not self.forking_user.admin:
            # Ditto, a new project can only be created in one's own namespace
            # (or by a copr maintainer, as CoprsLogic.add() allows, too).
            raise exceptions.InsufficientRightsException(
                "You can create a new project only in your own namespace.")

    def fork_copr(self, src_copr):
        """
        Return the destination project to fork src_copr into;  a copy of
        src_copr settings/chroots when it has to be created, the existing
        project otherwise (its settings are kept intact in that case).
        Packages and builds are not forked here, see fork_package() and
        fork_build().
        """
        dst_copr = self.get_destination()
        self.raise_if_cant_fork_into(dst_copr)

        if dst_copr and src_copr.storage != dst_copr.storage:
            raise exceptions.CoprHttpException(
                "Cannot fork a project from one storage to another")

        if not dst_copr:
            dst_copr = self.create_object(
                models.Copr, src_copr,
                exclude=["id", "group_id", "created_on",
                         "scm_repo_url", "scm_api_type", "scm_api_auth_json",
                         "persistent", "auto_prune", "contact",
                         "webhook_secret"])
            db.session.add(dst_copr)

            dst_copr.forked_from_id = src_copr.id
            dst_copr.user = self.dst_user
            dst_copr.created_on = int(time.time())
            if self.dst_name:
                dst_copr.name = self.dst_name
            if self.dst_group:
                dst_copr.group = self.dst_group
                dst_copr.group_id = self.dst_group.id

            dst_copr_dir = models.CoprDir(name=dst_copr.name, copr=dst_copr,
                                          main=True)
            db.session.add(dst_copr_dir)

            for src_chroot in list(src_copr.active_copr_chroots):
                CoprChrootsLogic.create_chroot_from(src_chroot,
                                                    mock_chroot=src_chroot.mock_chroot,
                                                    copr=dst_copr)

        return dst_copr

    def fork_package(self, src_package, dst_copr):
        """
        Fork src_package into the dst_copr project, and return the new (or
        the already existing) package.  The destination project is an
        argument here, this can be used without fork_copr().
        """
        dst_package = PackagesLogic.get(dst_copr.id, src_package.name).first()
        if not dst_package:
            dst_package = self.create_object(
                models.Package, src_package,
                exclude=["id", "copr_id", "webhook_rebuild"])
            dst_package.copr = dst_copr
            db.session.add(dst_package)
        return dst_package

    def fork_build(self, src_build, dst_copr, dst_package, src_chroots):
        """
        Fork src_build (only its src_chroots) into the dst_copr/dst_package,
        and return the new build.  Ditto, the destination is an argument so
        that this can be used on its own.
        """
        dst_build = self.create_object(
            models.Build, src_build,
            exclude=["id", "copr_id", "copr_dir_id", "package_id",
                     "result_dir"])
        db.session.add(dst_build)
        dst_build.copr = dst_copr
        dst_build.package = dst_package
        dst_build.copr_dir = dst_copr.main_dir
        dst_build.source_status = StatusEnum("forked")

        dst_build.result_dir = '{:08}'.format(dst_build.id)
        dst_build.build_chroots = [
            self.create_object(models.BuildChroot, c,
                               exclude=["id", "build_id", "result_dir",
                                        "copr_chroot_id"])
            for c in src_chroots
        ]
        for dst_chroot in dst_build.build_chroots:
            dst_chroot.result_dir = '{:08}-{}'.format(dst_build.id,
                                                      dst_package.name)
            dst_chroot.status = StatusEnum("forked")
            # the CoprChroot could be disabled in project (when we fork directly
            # by fork_build(), without parent fork_copr(), hence one_or_none()
            dst_chroot.copr_chroot = CoprChrootsLogic.get_by_mock_chroot_id(
                dst_copr,
                dst_chroot.mock_chroot_id,
            ).one_or_none()
        db.session.add(dst_build)
        return dst_build

    def create_object(self, clazz, from_object, exclude=list()):
        arguments = {}
        for name, column in from_object.__mapper__.columns.items():
            if not name in exclude:
                arguments[name] = getattr(from_object, name)
        return clazz(**arguments)


class BuildConfigLogic(object):
    @classmethod
    def generate_build_config(cls, coprdir, chroot_id):
        """ Return dict with proper build config contents """
        copr = coprdir.copr
        chroot = None
        for i in copr.active_copr_chroots:
            if i.mock_chroot.name == chroot_id:
                chroot = i
                break
        if not chroot:
            return {}

        packages = "" if not chroot.buildroot_pkgs else chroot.buildroot_pkgs

        repos = [{
            "id": "copr_base",
            "baseurl": copr.repo_url + "/{}/".format(chroot_id),
            "name": "Copr repository",
            "repo_gpgcheck": False,
        }]

        if copr.module_hotfixes:
            repos[0]["module_hotfixes"] = True

        if not copr.auto_createrepo:
            # On backend we use /devel but in Pulp we cannot create subdirectories
            suffix = "-devel" if copr.storage == StorageEnum.pulp else "/devel"
            baseurl = copr.repo_url + "/{0}{1}/".format(chroot_id, suffix)
            repos.append({
                "id": "copr_base_devel",
                "baseurl": baseurl,
                "name": "Copr buildroot",
                "repo_gpgcheck": False,
            })

        if not coprdir.main:
            repos.append({
                "id": "copr_coprdir",
                "baseurl": coprdir.repo_url + "/{}/".format(chroot_id),
                "name": "Coprdir repository",
                "repo_gpgcheck": False,
            })

        # None value of the priority won't show in API
        if copr.repo_priority in [None, DEFAULT_COPR_REPO_PRIORITY]:
            repo_priority = None
        else:
            repo_priority = copr.repo_priority

        for repo in repos:
            repo["priority"] = repo_priority

        repos.extend(cls.get_additional_repo_views(copr.repos_list, chroot_id))
        repos.extend(cls.get_additional_repo_views(chroot.repos_list, chroot_id))

        config_dict = {
            'project_id': copr.repo_id,
            'additional_packages': packages.split(),
            'repos': repos,
            'chroot': chroot_id,
            'with_opts': chroot.with_opts.split(),
            'without_opts': chroot.without_opts.split(),
        }
        config_dict.update(chroot.isolation_setup)
        config_dict.update(chroot.bootstrap_setup)
        return config_dict

    @classmethod
    def build_bootstrap_setup(cls, build_config, build):
        """ Get bootstrap setup from build_config, and override it by build """
        build_record = {}
        build_record["bootstrap"] = build_config.get("bootstrap", "default")
        build_record["bootstrap_image"] = build_config.get("bootstrap_image")

        # config overrides per-build
        if build.bootstrap_set:
            build_record["bootstrap"] = build.bootstrap

        # drop unnecessary (default) fields
        if build_record["bootstrap"] == "default":
            del build_record['bootstrap']
            del build_record['bootstrap_image']
        elif build_record["bootstrap"] != "custom_image":
            del build_record['bootstrap_image']
        return build_record

    @classmethod
    def get_build_isolation(cls, build_config, build):
        """ Get isolation setup from build_config, and override it by build """
        isolation = {"isolation": build_config.get("isolation", "default")}

        if build.isolation_set:
            isolation["isolation"] = build.isolation

        return isolation

    @classmethod
    def get_additional_repo_views(cls, repos_list, chroot_id):
        repos = []
        for repo in repos_list:
            params = parse_repo_params(repo)
            repo_view = {
                "id": generate_repo_name(repo),
                "baseurl": pre_process_repo_url(chroot_id, repo),
                "name": "Additional repo " + generate_repo_name(repo),
            }

            # We ask get_copr_by_repo() here only to resolve the
            # module_hotfixes attribute.  If the asked project doesn't exist, we
            # still adjust the 'repos' variable -- the build will eventually
            # fail on repo downloading, but at least the copr maintainer will be
            # notified about the misconfiguration.  Better than just skip the
            # repo.
            try:
                copr = ComplexLogic.get_copr_by_repo(repo)
            except ObjectNotFound:
                copr = None
            if copr:
                params["repo_gpgcheck"] = False
                if copr.module_hotfixes:
                    params["module_hotfixes"] = True

            repo_view.update(params)
            repos.append(repo_view)
        return repos

    @classmethod
    def generate_additional_repos(cls, copr_chroot):
        base_repo = "copr://{}".format(copr_chroot.copr.full_name)
        repos = [base_repo] + copr_chroot.repos_list + copr_chroot.copr.repos_list
        if not copr_chroot.copr.auto_createrepo:
            repos.append("copr://{}/devel".format(copr_chroot.copr.full_name))
        return repos


class ReposLogic:
    """
    Logic for generating repositories (e.g. in the project overview)
    """

    @classmethod
    def repos_for_copr(cls, copr,  copr_repo_dl_stat):
        """
        Return a `dict` containing repository information for all chroots in
        a given `copr` project
        """
        repos_groups = {}
        for chroot in copr.enable_permissible_copr_chroots:
            mc = chroot.mock_chroot
            repos_groups.setdefault(mc.name_release, [])
            repos_groups[mc.name_release].append(chroot)

        repos_info = {}
        for name_release, chroots in repos_groups.items():
            repo = cls.repo_for_chroots(chroots, copr_repo_dl_stat)
            repos_info[name_release] = repo
        cls._append_multilib_repos(copr, repos_info)
        return repos_info

    @classmethod
    def repo_for_chroots(cls, copr_chroots, copr_repo_dl_stat):
        """
        Return a repository that is combine for a multiple copr chroots. We
        show one repository for all architectures of the same name-release
        chroots
        """
        repo = None
        for chroot in copr_chroots:
            if not repo:
                repo = cls._basic_repo_for_chroot(chroot, copr_repo_dl_stat)

            arch = chroot.mock_chroot.arch
            repo["arch_list"].append(arch)
            repo["rpm_dl_stat"][arch] = cls._rpms_dl_stat(chroot)
            if chroot.delete_after_days is not None:
                repo["expirations"][arch] = chroot.delete_after_days

        repo["delete_reason"] = cls._delete_reason(copr_chroots)
        return repo

    @classmethod
    def _basic_repo_for_chroot(cls, copr_chroot, copr_repo_dl_stat):
        """
        Return a basic repository information for a given `copr_chroot`.
        Be aware that this information is incomplete and some
        architecture-specific parameters are not set.
        """
        copr = copr_chroot.copr
        mc = copr_chroot.mock_chroot
        return {
            "name_release": mc.name_release,
            "os_release": mc.os_release,
            "os_version": mc.os_version,
            "logo": cls._logo(mc),
            "arch_list": [],
            "repo_file": "{}-{}.repo".format(copr.repo_id, mc.name_release),
            "dl_stat": copr_repo_dl_stat[mc.name_release],
            "rpm_dl_stat": {},
            "delete_reason": None,
            "expirations": {},
        }

    @classmethod
    def _rpms_dl_stat(cls, copr_chroot):
        """
        Calculate how many times a repo for given `copr_chroot` was downloaded
        """
        stat_type = helpers.CounterStatType.CHROOT_RPMS_DL
        stat_name = helpers.get_stat_name(
            stat_type=stat_type,
            copr_chroot=copr_chroot,
        )
        stat = CounterStatLogic.get(stat_name).first()
        return stat.counter if stat else 0

    @classmethod
    def _delete_reason(cls, copr_chroots):
        """
        In case some of the `copr_chroots` is going to be deleted in the future,
        describe the reason why
        TODO: merge with the `CoprChroot.delete_status` property
        """
        # Do we even want to show a trash icon? I.e. are any of the project
        # chroots set to be deleted in the future?
        delete_chroots = [cc for cc in copr_chroots if cc.delete_status]
        if not delete_chroots:
            return None

        # Let's find out for what reason each of the chroot architecture is
        # going to be deleted and how much time is remaining before deletion.
        # (e.g. one architecture may be EOL and another may be deleted by the
        # project owner. Or all of them for the same reason. Also all
        # architectures may be deleted by the project owner but on a different
        # day and therefore the remaining time may be different)
        # See https://docs.copr.fedorainfracloud.org/developer_documentation/eol-logic.html
        reasons = {}
        for chroot in delete_chroots:
            reason_format = "{0} and will remain available for another {1} days"
            reason = "EOL"
            if chroot.is_active:
                if chroot.deleted and chroot.delete_after is not None:
                    reason = "disabled by a project owner"
                elif chroot.mock_chroot.rolling:
                    reason = "a rolling chroot inactive for a long time"
                else:
                    raise exceptions.BadRequest(f"Unknown EOL reason {chroot.name}")
            reason = reason_format.format(reason, chroot.delete_after_days)
            reasons.setdefault(reason, [])
            reasons[reason].append(chroot.mock_chroot.arch)

        # Since we have architectures grouped by reasons why they are going to
        # be deleted, let's create complete sentences describing them.
        full_reasons = []
        for key, value in reasons.items():
            pluralized = helpers.pluralize("The chroot", value, be_suffix=True)
            full_reasons.append("{0} {1}".format(pluralized, key))

        return "\n".join(full_reasons)

    @classmethod
    def _logo(cls, mock_chroot):
        """
        Assign the correct OS logo for this repository
        """
        logoset = set()
        logodir = app.static_folder + "/chroot_logodir"
        for entry in os.scandir(logodir):
            logo = entry.name
            # glob.glob() uses listdir() and fnmatch anyways
            if fnmatch.fnmatch(logo, "*.png"):
                logoset.add(logo[:-4])

        logo = None
        if mock_chroot.name_release in logoset:
            logo = mock_chroot.name_release + ".png"
        elif mock_chroot.os_release in logoset:
            logo = mock_chroot.os_release + ".png"
        elif mock_chroot.os_family in logoset:
            logo = mock_chroot.os_family + ".png"

        return logo

    @classmethod
    def _append_multilib_repos(cls, copr, repos_info):
        if not copr.multilib:
            return

        for name_release in repos_info:
            arches = repos_info[name_release]['arch_list']
            arch_repos = {}
            for ch64, ch32 in models.MockChroot.multilib_pairs.items():
                if set([ch64, ch32]).issubset(set(arches)):
                    arch_repos[ch64] = ch32

            repos_info[name_release]['arch_repos'] = arch_repos
