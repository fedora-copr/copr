# coding: utf-8

import os
import datetime
import time
import fnmatch
import flask
import sqlalchemy

from copr_common.enums import StatusEnum
from coprs import app
from coprs import db
from coprs import helpers
from coprs import models
from coprs import exceptions
from coprs import cache
from coprs.exceptions import ObjectNotFound, ActionInProgressException
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.batches_logic import BatchesLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.stat_logic import CounterStatLogic

from coprs.logic.users_logic import UsersLogic
from coprs.models import User, Copr
from coprs.logic.coprs_logic import (CoprsLogic, CoprDirsLogic, CoprChrootsLogic,
                                     PinnedCoprsLogic, MockChrootsLogic)


@sqlalchemy.event.listens_for(models.Copr.deleted, "set")
def unpin_projects_on_delete(copr, deleted, oldvalue, event):
    if not deleted:
        return
    PinnedCoprsLogic.delete_by_copr(copr)


class ComplexLogic(object):
    """
    Used for manipulation which affects multiply models
    """

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
            user = copr.user
        else:
            user = flask.g.user

        builds_query = BuildsLogic.get_multiple_by_copr(copr=copr)

        if copr.persistent:
            raise exceptions.InsufficientRightsException("This project is protected against deletion.")

        for build in builds_query:
            # Don't send delete action for each build, rather send an action to delete
            # a whole project as a part of CoprsLogic.delete_unsafe() method.
            BuildsLogic.delete_build(user, build, send_delete_action=False)

        CoprsLogic.delete_unsafe(user, copr)


    @classmethod
    def delete_expired_projects(cls):
        query = (
            models.Copr.query
            .filter(models.Copr.delete_after.isnot(None))
            .filter(models.Copr.delete_after < datetime.datetime.now())
            .filter(models.Copr.deleted.isnot(True))
        )
        for copr in query.all():
            print("deleting project '{}'".format(copr.full_name))
            try:
               cls.delete_copr(copr, admin_action=True)
            except ActionInProgressException as e:
                print(e)
                print("project {} postponed".format(copr.full_name))


    @classmethod
    def fork_copr(cls, copr, user, dstname, dstgroup=None):
        forking = ProjectForking(user, dstgroup)
        created = (not bool(forking.get(copr, dstname)))
        fcopr = forking.fork_copr(copr, dstname)

        if fcopr.full_name == copr.full_name:
            raise exceptions.DuplicateException("Source project should not be same as destination")

        builds_map = {}
        srpm_builds_src = []
        srpm_builds_dst = []

        for package in copr.packages:
            fpackage = forking.fork_package(package, fcopr)

            builds = PackagesLogic.last_successful_build_chroots(package)
            if not builds:
                continue

            for build, build_chroots in builds.items():
                fbuild = forking.fork_build(build, fcopr, fpackage, build_chroots)

                if build.result_dir:
                    srpm_builds_src.append(build.result_dir)
                    srpm_builds_dst.append(fbuild.result_dir)

                for chroot, fchroot in zip(build_chroots, fbuild.build_chroots):
                    if not chroot.result_dir:
                        continue
                    if chroot.name not in builds_map:
                        builds_map[chroot.name] = {chroot.result_dir: fchroot.result_dir}
                    else:
                        builds_map[chroot.name][chroot.result_dir] = fchroot.result_dir

        builds_map['srpm-builds'] = dict(zip(srpm_builds_src, srpm_builds_dst))

        db.session.commit()
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
        """ Get one project.

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
    def get_copr_by_repo_safe(repo_url):
        copr_repo = helpers.copr_repo_fullname(repo_url)
        if not copr_repo:
            return None
        try:
            owner, copr = copr_repo.split("/")
        except:
            # invalid format, e.g. multiple slashes in copr_repo
            return None
        return ComplexLogic.get_copr_by_owner_safe(owner, copr)

    @staticmethod
    def get_copr_dir_safe(ownername, copr_dirname, **kwargs):
        try:
            return CoprDirsLogic.get_by_ownername(ownername, copr_dirname).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise ObjectNotFound(message="copr dir {}/{} does not exist."
                        .format(ownername, copr_dirname))

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
        except (sqlalchemy.orm.exc.NoResultFound,
                sqlalchemy.exc.DataError):
            raise ObjectNotFound(
                message="Build {} does not exist.".format(build_id))

    @staticmethod
    def get_build_chroot(build_id, chrootname):
        """
        Return a `models.BuildChroot` instance based on build ID and name of the chroot.
        If there is no such chroot, `ObjectNotFound` execption is raised.
        """
        build = ComplexLogic.get_build_safe(build_id)
        try:
            return build.chroots_dict_by_name[chrootname]
        except KeyError:
            msg = "Build {} was not submitted to {} chroot.".format(build_id, chrootname)
            if not MockChrootsLogic.get_from_name(chrootname).one_or_none():
                msg = "Chroot {} does not exist".format(chrootname)
            raise ObjectNotFound(message=msg)

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
            fcopr = self.create_object(models.Copr, copr,
                                       exclude=["id", "group_id", "created_on",
                                                "scm_repo_url", "scm_api_type", "scm_api_auth_json",
                                                "persistent", "auto_prune", "contact", "webhook_secret"])

            fcopr.forked_from_id = copr.id
            fcopr.user = self.user
            fcopr.created_on = int(time.time())
            if name:
                fcopr.name = name
            if self.group:
                fcopr.group = self.group
                fcopr.group_id = self.group.id

            fcopr_dir = models.CoprDir(name=fcopr.name, copr=fcopr, main=True)

            for chroot in list(copr.active_copr_chroots):
                CoprChrootsLogic.create_chroot_from(chroot,
                                                    mock_chroot=chroot.mock_chroot,
                                                    copr=fcopr)

            db.session.add(fcopr)
            db.session.add(fcopr_dir)

        return fcopr

    def fork_package(self, package, fcopr):
        fpackage = PackagesLogic.get(fcopr.id, package.name).first()
        if not fpackage:
            fpackage = self.create_object(models.Package, package, exclude=["id", "copr_id", "webhook_rebuild"])
            fpackage.copr = fcopr
            db.session.add(fpackage)
        return fpackage

    def fork_build(self, build, fcopr, fpackage, build_chroots):
        fbuild = self.create_object(models.Build, build, exclude=["id", "copr_id", "copr_dir_id", "package_id", "result_dir"])
        fbuild.copr = fcopr
        fbuild.package = fpackage
        fbuild.copr_dir = fcopr.main_dir
        fbuild.source_status = StatusEnum("forked")
        db.session.add(fbuild)
        db.session.flush()

        fbuild.result_dir = '{:08}'.format(fbuild.id)
        fbuild.build_chroots = [
            self.create_object(models.BuildChroot, c,
                               exclude=["id", "build_id", "result_dir",
                                        "copr_chroot_id"])
            for c in build_chroots
        ]
        for chroot in fbuild.build_chroots:
            chroot.result_dir = '{:08}-{}'.format(fbuild.id, fpackage.name)
            chroot.status = StatusEnum("forked")
            # the CoprChroot could be disabled in project (when we fork directly
            # by fork_build(), without parent fork_copr(), hence one_or_none()
            chroot.copr_chroot = CoprChrootsLogic.get_by_mock_chroot_id(
                fcopr,
                chroot.mock_chroot_id,
            ).one_or_none()
        db.session.add(fbuild)
        return fbuild

    def create_object(self, clazz, from_object, exclude=list()):
        arguments = {}
        for name, column in from_object.__mapper__.columns.items():
            if not name in exclude:
                arguments[name] = getattr(from_object, name)
        return clazz(**arguments)


class BuildConfigLogic(object):

    @classmethod
    def generate_build_config(cls, copr, chroot_id):
        """ Return dict with proper build config contents """
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
        }]

        if copr.module_hotfixes:
            repos[0]["module_hotfixes"] = True

        if not copr.auto_createrepo:
            repos.append({
                "id": "copr_base_devel",
                "baseurl": copr.repo_url + "/{}/devel/".format(chroot_id),
                "name": "Copr buildroot",
            })

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
            params = helpers.parse_repo_params(repo)
            repo_view = {
                "id": helpers.generate_repo_name(repo),
                "baseurl": helpers.pre_process_repo_url(chroot_id, repo),
                "name": "Additional repo " + helpers.generate_repo_name(repo),
            }

            # We ask get_copr_by_repo_safe() here only to resolve the
            # module_hotfixes attribute.  If the asked project doesn't exist, we
            # still adjust the 'repos' variable -- the build will eventually
            # fail on repo downloading, but at least the copr maintainer will be
            # notified about the misconfiguration.  Better than just skip the
            # repo.
            try:
                copr = ComplexLogic.get_copr_by_repo_safe(repo)
            except ObjectNotFound:
                copr = None
            if copr and copr.module_hotfixes:
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
        reasons = {}
        for chroot in delete_chroots:
            reason_format = "{0} and will remain available for another {1} days"
            reason = reason_format.format(
                "disabled by a project owner" if chroot.is_active else "EOL",
                chroot.delete_after_days,
            )
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
        for logo in os.listdir(logodir):
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
