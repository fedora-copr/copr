#!/usr/bin/python
# -*- coding: utf-8 -*-

# RUN
#     cd frontend/coprs_frontend
#     COPR_CONFIG=../config/copr_devel.conf python run/migrate-copr.py

# NOTES
# - We do have to copy user, group and some other (see mods variable) tables
# - Stage 0 - Cleaning


from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import os
here = os.path.dirname(os.path.realpath(__file__))
import sys
sys.path.append(os.path.dirname(here))

import flask
from flask_sqlalchemy import SQLAlchemy
from coprs import app, models, db, logic, helpers
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.packages_logic import PackagesLogic


DSTDB_CONFIG = {"username": "copr-fe", "password": "coprpass", "host": "127.0.0.1", "database": "coprdbnew"}
srcdb = db

dstapp = flask.Flask(__name__)
dstapp.config.from_object("coprs.config.DevelopmentConfig")
dstapp.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://{username}:{password}@{host}/{database}".format(**DSTDB_CONFIG)
dstdb = SQLAlchemy(dstapp)


def all_coprs():
    """ Return all coprs without those which are deleted. """
    return CoprsLogic.get_all()


class Copying(object):
    def __init__(self, dstdb):
        self.dstdb = dstdb

    def create_object(self, clazz, from_object, exclude=list()):
        arguments = {}
        for name, column in from_object.__mapper__.columns.items():
            if not name in exclude:
                arguments[name] = getattr(from_object, name)
        return clazz(**arguments)

    def copy_objects(self, model):
        for obj in srcdb.session.query(model).all():
            new = self.create_object(model, obj)
            dstdb.session.add(new)

    def copy_build(self, build):
        if build:
            new = self.create_object(models.Build, build, exclude=["id"])
            new.build_chroots = [self.create_object(models.BuildChroot, c, exclude=["id"]) for c in build.build_chroots]
            dstdb.session.add(new)


# class MockDB():
#     def __init__(self, dstdb):
#         self.dstdb = dstdb
#         self.olddb = None
#
#     def __enter__(self):
#         self.olddb = logic.coprs_logic.db
#         logic.coprs_logic.db = self.dstdb
#
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         logic.coprs_logic.db = self.olddb


mods = [
    models.User,
    models.Group,
    models.Copr,
    models.CoprPermission,
    models.CoprChroot,
    models.Package,
    models.MockChroot,
]

clean_mods = [
    models.LegalFlag,
    models.BuildChroot,
    models.Build,
] + list(reversed(mods))


# Stage 0 - Cleaning
def clean(db):
    for model in clean_mods:
        db.session.query(model).delete()


# Stage 1 - Copy data (projects, packages, last successfull build from each package)
def copy_data(cp):
    for model in mods:
        cp.copy_objects(model)

    for copr in all_coprs():
        for package in PackagesLogic.get_all(copr.id):
            cp.copy_build(package.last_build(successful=True))


# Stage 2 - succeeded -> [pending|importing]
def ensure_rebuild(dstdb):
    for chroot in dstdb.session.query(models.BuildChroot).all():
        chroot.status = helpers.StatusEnum("pending" if chroot.git_hash else "importing")


# Stage 3 - failed -> pending (repeat)
def rebuild_failed(dstdb):
    for i in range(1, 5):
        builds = dstdb.session.query(models.BuildChroot).filter_by(status=helpers.StatusEnum("failed")).all()
        for chroot in builds:
            chroot.status = helpers.StatusEnum("pending")


def main():
    # Stage 0 - Cleaning
    print("### Stage 0 - Cleaning ###################################")
    clean(dstdb)
    dstdb.session.commit()

    # Stage 1 - Copy data (projects, packages, last successfull build from each package)
    print("### Stage 1 - Copy data ##################################")
    cp = Copying(dstdb)
    copy_data(cp)
    dstdb.session.commit()

    # Stage 2 - succeeded -> [pending|importing]
    print("### Stage 2 - succeeded -> [pending|importing] ###########")
    ensure_rebuild(dstdb)
    dstdb.session.commit()

    # Stage 3 - failed -> pending (repeat)
    print("### Stage 3 - failed -> pending (repeat ##################")
    rebuild_failed(dstdb)
    dstdb.session.commit()


if __name__ == "__main__":
    main()
