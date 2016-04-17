import json
import time
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.sql import false, true

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers

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
