import json
import time
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
    def get_all(cls, copr_id):
        return (models.Package.query
                .filter(models.Package.copr_id == copr_id))

    @classmethod
    def get_copr_packages_list(cls, copr):
        query_select = """
SELECT package.name, build.pkg_version, build.submitted_on, package.webhook_rebuild, order_to_status(MIN(statuses.st)) AS status
FROM build
LEFT OUTER JOIN package ON build.package_id = package.id
LEFT OUTER JOIN (SELECT build_chroot.build_id, started_on, ended_on, status_to_order(status) AS st FROM build_chroot) AS statuses
  ON statuses.build_id=build.id
WHERE build.id IN
  (select id from (select MAX(build.id) as id, package.name as pkg_name
  from package
  left outer join build on build.package_id = package.id
  where build.copr_id = :copr_id
  group by package.name) as foo )
GROUP BY package.name, build.pkg_version, build.submitted_on, package.webhook_rebuild
ORDER BY package.name ASC;
"""

        if db.engine.url.drivername == "sqlite":
            def sqlite_status_to_order(x):
                if x == 0:
                    return 0
                elif x == 3:
                    return 1
                elif x == 6:
                    return 2
                elif x == 7:
                    return 3
                elif x == 4:
                    return 4
                elif x == 1:
                    return 5
                elif x == 5:
                    return 6
                return 1000

            def sqlite_order_to_status(x):
                if x == 0:
                    return 0
                elif x == 1:
                    return 3
                elif x == 2:
                    return 6
                elif x == 3:
                    return 7
                elif x == 4:
                    return 4
                elif x == 5:
                    return 1
                elif x == 6:
                    return 5
                return 1000

            conn = db.engine.connect()
            conn.connection.create_function("status_to_order", 1, sqlite_status_to_order)
            conn.connection.create_function("order_to_status", 1, sqlite_order_to_status)
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            result = conn.execute(statement, {"copr_id": copr.id})
        else:
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            result = db.engine.execute(statement, {"copr_id": copr.id})

        return result

    @classmethod
    def get(cls, copr_id, package_name):
        return models.Package.query.filter(models.Package.copr_id == copr_id,
                                           models.Package.name == package_name)

    @classmethod
    def get_for_webhook_rebuild(cls, copr_id, webhook_secret, clone_url, commits):
        packages = (models.Package.query.join(models.Copr)
                    .filter(models.Copr.webhook_secret == webhook_secret)
                    .filter(models.Package.copr_id == copr_id)
                    .filter(models.Package.webhook_rebuild == true())
                    .filter(models.Package.source_json.contains(clone_url)))
        result = []
        for package in packages:
            if cls.commits_belong_to_package(package, commits):
                result += [package]
        return result

    @classmethod
    def commits_belong_to_package(cls, package, commits):
        if package.source_type_text == "git_and_tito":
            for commit in commits:
                for file_path in commit['added'] + commit['removed'] + commit['modified']:
                    if cls.path_belong_to_package(package, file_path):
                        return True
            return False
        return True

    @classmethod
    def path_belong_to_package(cls, package, file_path):
        if package.source_type_text == "git_and_tito":
            data = package.source_json_dict
            return file_path.startswith(data["git_dir"] or '')
        else:
            return True

    @classmethod
    def add(cls, user, copr, package_name, source_type=helpers.BuildSourceEnum("unset"), source_json=json.dumps({})):
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        if cls.exists(copr.id, package_name).all():
            raise exceptions.DuplicateException(
                "Project {}/{} already has a package '{}'"
                .format(copr.owner_name, copr.name, package_name))

        package = models.Package(
            name=package_name,
            copr_id=copr.id,
            source_type=source_type,
            source_json=source_json
        )

        db.session.add(package)

        return package

    @classmethod
    def exists(cls, copr_id, package_name):
        return (models.Package.query
                .filter(models.Package.copr_id == copr_id)
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
            raise NoPackageSourceException('Unset default source for package {package}'.format(package.name))
        return builds_logic.BuildsLogic.create_new(user, copr, package.source_type, package.source_json, chroot_names, **build_options)
