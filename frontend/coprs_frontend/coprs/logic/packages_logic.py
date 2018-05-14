import ujson as json
import time
import re

from sqlalchemy import or_
from sqlalchemy import and_, bindparam, Integer
from sqlalchemy.sql import false, true, text

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers
from coprs import forms

from coprs.logic import coprs_logic
from coprs.logic import users_logic
from coprs.logic import builds_logic

from coprs.constants import DEFAULT_BUILD_TIMEOUT

log = app.logger


class PackagesLogic(object):

    @classmethod
    def get_by_id(cls, package_id):
        return models.Package.query.filter(models.Package.id == package_id)

    @classmethod
    def get_all(cls, copr_dir_id):
        return (models.Package.query
                .filter(models.Package.copr_dir_id == copr_dir_id))

    @classmethod
    def get_all_in_copr(cls, copr_id):
        return (models.Package.query
                .filter(models.Package.copr_id == copr_id))

    @classmethod
    def get_copr_packages_list(cls, copr_dir):
        query_select = """
SELECT package.name, build.pkg_version, build.submitted_on, package.webhook_rebuild, order_to_status(subquery2.min_order_for_a_build) AS status, build.source_status
FROM package
LEFT OUTER JOIN (select MAX(build.id) as max_build_id_for_a_package, package_id
  FROM build
  WHERE build.copr_dir_id = :copr_dir_id
  GROUP BY package_id) as subquery1 ON subquery1.package_id = package.id
LEFT OUTER JOIN build ON build.id = subquery1.max_build_id_for_a_package
LEFT OUTER JOIN (select build_id, min(status_to_order(status)) as min_order_for_a_build
  FROM build_chroot
  GROUP BY build_id) as subquery2 ON subquery2.build_id = subquery1.max_build_id_for_a_package
WHERE package.copr_dir_id = :copr_dir_id;
        """

        if db.engine.url.drivername == "sqlite":
            def sqlite_status_to_order(x):
                if x == 3:
                    return 1
                elif x == 6:
                    return 2
                elif x == 7:
                    return 3
                elif x == 4:
                    return 4
                elif x == 0:
                    return 5
                elif x == 1:
                    return 6
                elif x == 5:
                    return 7
                elif x == 2:
                    return 8
                elif x == 8:
                    return 9
                elif x == 9:
                    return 10
                return 1000

            def sqlite_order_to_status(x):
                if x == 1:
                    return 3
                elif x == 2:
                    return 6
                elif x == 3:
                    return 7
                elif x == 4:
                    return 4
                elif x == 5:
                    return 0
                elif x == 6:
                    return 1
                elif x == 7:
                    return 5
                elif x == 8:
                    return 2
                elif x == 9:
                    return 8
                elif x == 10:
                    return 9
                return 1000

            conn = db.engine.connect()
            conn.connection.create_function("status_to_order", 1, sqlite_status_to_order)
            conn.connection.create_function("order_to_status", 1, sqlite_order_to_status)
            statement = text(query_select)
            statement.bindparams(bindparam("copr_dir_id", Integer))
            result = conn.execute(statement, {"copr_dir_id": copr_dir.id})
        else:
            statement = text(query_select)
            statement.bindparams(bindparam("copr_dir_id", Integer))
            result = db.engine.execute(statement, {"copr_dir_id": copr_dir.id})

        return result

    @classmethod
    def get_list_by_copr(cls, copr_id, package_name):
        return models.Package.query.filter(models.Package.copr_id == copr_id,
                                           models.Package.name == package_name)

    @classmethod
    def get(cls, copr_dir_id, package_name):
        return models.Package.query.filter(models.Package.copr_dir_id == copr_dir_id,
                                           models.Package.name == package_name)

    @classmethod
    def get_by_dir_name(cls, copr_dir_name, package_name):
        return models.Package.query.join(models.CoprDir).filter(
            models.CoprDir.name == copr_dir_name, models.Package.name == package_name)

    @classmethod
    def get_or_create(cls, copr_dir, package_name, src_pkg):
        package = cls.get_by_dir_name(copr_dir.name, package_name).first()

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
    def get_for_webhook_rebuild(cls, copr_id, webhook_secret, clone_url, commits, ref_type, ref):
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

            if cls.commits_belong_to_package(package, commits, ref_type, ref):
                result += [package]

        return result

    @classmethod
    def commits_belong_to_package(cls, package, commits, ref_type, ref):
        if ref_type == "tag":
            matches = re.search(r'(.*)-[^-]+-[^-]+$', ref)
            if matches and package.name != matches.group(1):
                return False
            else:
                return True

        committish = package.source_json_dict.get("committish") or ''
        if committish and not ref.endswith(committish):
            return False

        path_match = True
        for commit in commits:
            for file_path in commit['added'] + commit['removed'] + commit['modified']:
                path_match = False
                if cls.path_belong_to_package(package, file_path):
                    path_match = True
                    break
        if not path_match:
            return False

        return True

    @classmethod
    def path_belong_to_package(cls, package, file_path):
        data = package.source_json_dict
        norm_file_path = file_path.strip('./')
        package_subdir = data.get('subdirectory') or ''
        return norm_file_path.startswith(package_subdir.strip('./'))

    @classmethod
    def add(cls, user, copr_dir, package_name, source_type=helpers.BuildSourceEnum("unset"), source_json=json.dumps({})):
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr_dir.copr,
            "You don't have permissions to build in this copr.")

        if cls.exists(copr_dir.id, package_name).all():
            raise exceptions.DuplicateException(
                "Project dir {} already has a package '{}'"
                .format(copr_dir.full_name, package_name))

        package = models.Package(
            name=package_name,
            copr=copr_dir.copr,
            copr_dir=copr_dir,
            source_type=source_type,
            source_json=source_json,
        )

        db.session.add(package)
        return package

    @classmethod
    def exists(cls, copr_dir_id, package_name):
        return (models.Package.query
                .filter(models.Package.copr_dir_id == copr_dir_id)
                .filter(models.Package.name == package_name))


    @classmethod
    def delete_package(cls, user, package):
        if not user.can_edit(package.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete package `{}`.".format(package.id))

        for build in package.builds:
            builds_logic.BuildsLogic.delete_build(user, build)

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
    def build_package(cls, user, copr, package, chroot_names=None, **build_options):
        if not package.has_source_type_set or not package.source_json:
            raise exceptions.NoPackageSourceException('Unset default source for package {0}'.format(package.name))
        return builds_logic.BuildsLogic.create_new(user, copr, package.source_type, package.source_json, chroot_names, **build_options)


    @classmethod
    def batch_build(cls, user, copr, packages, chroot_names=None, **build_options):
        new_builds = []

        batch = models.Batch()
        db.session.add(batch)

        for package in packages:
            git_hashes = {}
            skip_import = False
            source_build = None

            if (package.source_type == helpers.BuildSourceEnum('upload') or
                    package.source_type == helpers.BuildSourceEnum('link')):
                source_build = package.last_build()

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
                git_hashes=git_hashes,
                skip_import=skip_import,
                batch=batch,
                **build_options)

            if source_build:
                new_build.package_id = source_build.package_id
                new_build.pkg_version = source_build.pkg_version

            new_builds.append(new_build)

        return new_builds
