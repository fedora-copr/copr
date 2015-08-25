# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint
from coprs.exceptions import InsufficientRightsException
from coprs.rest_api.exceptions import AccessForbidden, ObjectNotFoundError
from coprs.rest_api.resources.project import rest_api_auth_required
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one
from ... import db


def render_copr_chroot(chroot):
    return {
        "chroot": mm_serialize_one(CoprChrootSchema, chroot),
        "_links": {
            "project": {"href": url_for(".projectr", project_id=chroot.copr.id)},
            "self": {"href": url_for(".projectchrootr",
                                     project_id=chroot.copr.id,
                                     name=chroot.name)},
        }
    }


class ProjectChrootListR(Resource):

    def get(self, project_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        return {
            "chroots": [
                render_copr_chroot(chroot)
                for chroot in copr.copr_chroots
            ],
            "_links": {
                "self": {"href": url_for(".projectchrootlistr", project_id=project_id)}
            }
        }


class ProjectChrootR(Resource):

    def get(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = get_one_safe(CoprChrootsLogic.get_by_name(copr, name))

        return render_copr_chroot(chroot)

    @rest_api_auth_required
    def delete(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = CoprChrootsLogic.get_by_name_safe(copr, name)

        if chroot:
            try:
                CoprChrootsLogic.remove_copr_chroot(flask.g.user, chroot)
            except InsufficientRightsException as err:
                raise AccessForbidden("Failed to remove copr chroot: {}".format(err))

            db.session.commit()

        return "", 204

    @rest_api_auth_required
    def put(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = get_one_safe(CoprChrootsLogic.get_by_name(copr, name))

        chroot_data = mm_deserialize(CoprChrootSchema(), flask.request.data)
        updated_chroot = CoprChrootsLogic.update_chroot(
            user=flask.g.user,
            copr_chroot=chroot,
            **chroot_data.data
        )

        db.session.commit()
        return render_copr_chroot(updated_chroot)
