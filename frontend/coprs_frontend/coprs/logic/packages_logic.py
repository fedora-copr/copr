import json
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.sql import false

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers

from coprs.logic import coprs_logic
from coprs.logic import users_logic

log = app.logger


class PackagesLogic(object):
    @classmethod
    def get_all(cls, copr_id):
        return (models.Package.query
                    .filter(models.Package.copr_id == copr_id)
                    .filter(models.Package.name == package_name))

    @classmethod
    def get(cls, copr_id, package_name):
        return models.Package.query.filter(models.Package.copr_id == copr_id,
                                           models.Package.name == package_name)

    @classmethod
    def add(cls, user, copr, package_name):
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        if cls.exists(copr.id, package_name).all():
            raise exceptions.DuplicateException(
                "Project {}/{} already has a package '{}'".format(
                                                            copr.owner.name,
                                                            copr.name,
                                                            package_name))

        source_type = helpers.BuildSourceEnum("unset")
        source_json = json.dumps({})

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
        existing = (models.Package.query
                    .filter(models.Package.copr_id == copr_id)
                    .filter(models.Package.name == package_name))

        return existing
