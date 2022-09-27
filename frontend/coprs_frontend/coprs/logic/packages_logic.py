import json
import re
from typing import List, Optional

from sqlalchemy import bindparam, Integer, func
from sqlalchemy.sql import true, text
from sqlalchemy.orm import selectinload

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers

from coprs.logic import users_logic
from coprs.logic import builds_logic
from coprs.models import Package
from copr_common.enums import StatusEnum

log = app.logger


class PackagesLogic(object):

    @classmethod
    def get_by_id(cls, package_id):
        return models.Package.query.filter(models.Package.id == package_id)

    @classmethod
    def get_all(cls, copr_id):
        """
        Get all packages assigned to given project ID.
        """
        return (models.Package.query
                .filter(models.Package.copr_id == copr_id))

    @classmethod
    def get_all_ordered(cls, copr_id):
        """
        Get all packages in given project ID.
        """
        return cls.get_all(copr_id).order_by(models.Package.name)

    @classmethod
    def get_packages_with_latest_builds_for_dir(
            cls, copr_dir, small_build=True, packages=None):
        """
        Obtain the list of package objects for given copr_dir, with the
        latest build assigned.
        Parameters:

        :param copr_dir: CoprDir ID (int)
        :param small_build: Don't assign full Build objects, but only a limited
            objects with necessary info.
        :param packages: Don't query the list of Package objects from DB, but
            use the given 'packages' array.
        :return: array of Package objects, with assigned latest Build object
        """
        if packages is None:
            packages = cls.get_all_ordered(copr_dir.copr.id).all()

        pkg_ids = [package.id for package in packages]
        builds_ids = (
            models.Build.query.join(models.CoprDir)
            .filter(models.Build.package_id.in_(pkg_ids))
            .filter(models.CoprDir.id==copr_dir.id)
            .with_entities(func.max(models.Build.id))
            .group_by(models.Build.package_id)
        )

        # map package.id => package object in packages array
        packages_map = {package.id: package for package in packages}

        builds = (models.Build.query.filter(models.Build.id.in_(builds_ids))
                  .options(selectinload('build_chroots'))
                  .yield_per(1000))

        for build in builds:
            class SmallBuild():
                pass

            if not build.package_id:
                continue

            if small_build:
                small_build_object = SmallBuild()
                for param in ['state', 'status', 'pkg_version',
                              'submitted_on']:
                    # we don't want to keep all the attributes here in memory, and
                    # also we don't need any further info about assigned
                    # build_chroot(s).  So we only pick the info we need, and throw
                    # the expensive objects away.
                    setattr(small_build_object, param, getattr(build, param))
                packages_map[build.package_id].latest_build = small_build_object
            else:
                packages_map[build.package_id].latest_build = build


        return packages

    @classmethod
    def get_list_by_copr(cls, copr_id, package_name):
        return models.Package.query.filter(models.Package.copr_id == copr_id,
                                           models.Package.name == package_name)

    @classmethod
    def get(cls, copr_id, package_name):
        return models.Package.query.filter(models.Package.copr_id == copr_id,
                                           models.Package.name == package_name)

    @classmethod
    def get_by_dir(cls, copr_dir, package_name):
        return models.Package.query.join(models.CoprDir).filter(
            models.CoprDir.id==copr_dir.id,
            models.Package.name==package_name
        )

    @classmethod
    def get_or_create(cls, copr_dir, package_name, src_pkg):
        package = cls.get_by_dir(copr_dir, package_name).first()

        if package:
            return package

        package = models.Package(
            name=src_pkg.name,
            copr=src_pkg.copr,
            source_type=src_pkg.source_type,
            source_json=src_pkg.source_json,
            copr_dir=copr_dir)

        db.session.add(package)
        return package

    @classmethod
    def get_for_webhook_rebuild(
        cls, copr_id, webhook_secret, clone_url, commits, ref_type, ref, pkg_name: Optional[str]
    ) -> List[Package]:
        clone_url_stripped = re.sub(r'(\.git)?/*$', '', clone_url)

        packages = (models.Package.query.join(models.Copr)
                    .filter(models.Copr.webhook_secret == webhook_secret)
                    .filter(models.Package.source_type == helpers.BuildSourceEnum("scm"))
                    .filter(models.Package.copr_id == copr_id)
                    .filter(models.Package.webhook_rebuild == true())
                    .filter(models.Package.source_json.contains(clone_url_stripped)))

        result = []
        for package in packages:
            package_clone_url = package.source_json_dict.get('clone_url', '')
            package_clone_url_stripped = re.sub(r'(\.git)?/*$', '', package_clone_url)

            if package_clone_url_stripped != clone_url_stripped:
                continue

            if not package.copr.active_copr_chroots:
                continue

            if cls._belongs_to_package(package, commits, ref_type, ref, pkg_name):
                result.append(package)

        return result

    @classmethod
    def _belongs_to_package(
        cls, package: Package, commits, ref_type: str, ref: str, pkg_name: Optional[str]
    ) -> bool:
        if ref_type == "tag":
            return cls._tag_belongs_to_package(package, ref, pkg_name)

        return cls.commits_belong_to_package(package, commits, ref)

    @staticmethod
    def _ref_matches_copr_pkgname(ref: str, copr_pkg_name: str) -> bool:
        """
        We accept N-V-R and N-V.  Version and Release needs to contain at least one
        digit.
        """
        separators = ["-", "_"]

        def _parts_match(ref_parts):
            return any(separator.join(ref_parts) == copr_pkg_name for separator in separators)

        def _has_a_version_part(ref_parts):
            if len(ref_parts) < 2:
                return False
            return any(char.isdigit() for char in ref_parts[-1])

        for sep in separators:
            parts = ref.split(sep)
            # in case that ref has both version and release we need to do this twice
            for _ in range(2):
                if not _has_a_version_part(parts):
                    break
                # drop the last version component, and compare
                parts.pop()
                if _parts_match(parts):
                    return True

        return False

    @classmethod
    def _tag_belongs_to_package(
        cls, package: Package, ref: str, pkg_name: Optional[str]
    ) -> bool:
        if package.name == pkg_name:
            return True

        return cls._ref_matches_copr_pkgname(ref, package.name)

    @classmethod
    def commits_belong_to_package(cls, package: Package, commits, ref: str) -> bool:
        committish = package.source_json_dict.get("committish") or ''
        if committish and not ref.endswith(committish):
            return False

        for commit in commits:
            subdir = package.source_json_dict.get('subdirectory')
            sm = helpers.SubdirMatch(subdir)
            changed = set()
            for ch in ['added', 'removed', 'modified']:
                changed |= set(commit.get(ch, []))

            for file_path in changed:
                if sm.match(file_path):
                    return True

        return False

    @classmethod
    def add(cls, user, copr, package_name, source_type=helpers.BuildSourceEnum("unset"), source_json=json.dumps({})):
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        if cls.exists(copr, package_name).all():
            raise exceptions.DuplicateException(
                "Project {} already has a package '{}'"
                .format(copr.full_name, package_name))

        package = models.Package(
            name=package_name,
            copr=copr,
            source_type=source_type,
            source_json=source_json,
        )

        db.session.add(package)
        return package

    @classmethod
    def exists(cls, copr, package_name):
        return (models.Package.query
                .filter(models.Package.copr_id == copr.id)
                .filter(models.Package.name == package_name))


    @classmethod
    def delete_package(cls, user, package):
        if not user.can_edit(package.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete package `{}`.".format(package.id))

        to_delete = []
        for build in package.builds:
            to_delete.append(build.id)

        builds_logic.BuildsLogic.delete_builds(user, to_delete)
        db.session.delete(package)


    @classmethod
    def reset_package(cls, user, package):
        if not user.can_edit(package.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to reset package `{}`.".format(package.id))

        package.source_json = json.dumps({})
        package.source_type = helpers.BuildSourceEnum("unset")

        db.session.add(package)


    @classmethod
    def build_package(cls, user, copr, package, chroot_names=None, copr_dirname=None, **build_options):
        if not package.has_source_type_set or not package.source_json:
            raise exceptions.NoPackageSourceException('Unset default source for package {0}'.format(package.name))

        build = builds_logic.BuildsLogic.create_new(
            user, copr, package.source_type, package.source_json, chroot_names,
            copr_dirname=copr_dirname, package=package, **build_options)
        return build


    @classmethod
    def batch_build(cls, user, copr, packages, chroot_names=None,
                    only_package_chroots=None, **build_options):
        new_builds = []

        batch = models.Batch()
        db.session.add(batch)

        for package in packages:
            git_hashes = {}
            skip_import = False
            source_build = None

            if (package.source_type == helpers.BuildSourceEnum('upload') or
                    package.source_type == helpers.BuildSourceEnum('link')):
                source_build = package.last_build(successful=True)

                if not source_build or not source_build.build_chroots[0].git_hash:
                    raise exceptions.NoPackageSourceException(
                        "Could not get latest git hash for {}".format(package.name))

                for chroot_name in chroot_names:
                    git_hashes[chroot_name] = source_build.build_chroots[0].git_hash
                skip_import = True

            new_build = builds_logic.BuildsLogic.create_new(
                user,
                copr,
                package.source_type,
                package.source_json,
                chroot_names,
                package=package,
                git_hashes=git_hashes,
                skip_import=skip_import,
                batch=batch,
                package_chroots_subset=only_package_chroots,
                **build_options)

            if source_build:
                new_build.package_id = source_build.package_id
                new_build.pkg_version = source_build.pkg_version

            new_builds.append(new_build)

        return new_builds

    @classmethod
    def delete_orphaned_packages(cls):
        pkgs_to_delete = models.Package.query\
            .join(models.Copr, models.Package.copr_id == models.Copr.id)\
            .filter(models.Copr.deleted == True)

        counter = 0
        for pkg in pkgs_to_delete:
            cls.delete_package(pkg.copr.user, pkg)
            counter += 1
            if counter >= 100:
                db.session.commit()
                counter = 0

        if counter > 0:
            db.session.commit()

    @classmethod
    def last_successful_build_chroots(cls, package):
        builds = {}
        for chroot in package.chroots:
            for build in reversed(package.builds):
                try:
                    build_chroot = build.chroots_dict_by_name[chroot.name]
                except KeyError:
                    continue
                if build_chroot.status not in [StatusEnum("succeeded"), StatusEnum("forked")]:
                    continue
                if build not in builds:
                    builds[build] = [build_chroot]
                else:
                    builds[build].append(build_chroot)
                break
        return builds


    @classmethod
    def log_being_admin(cls, user, package):
        """
        Log if a package is being updated by a Copr maintainer
        """
        if helpers.being_server_admin(user, package.copr):
            app.logger.info("Admin '%s' using their permissions to update "
                            "package '%s' in project '%s'",
                            user.name,
                            package.name,
                            package.copr.full_name)
