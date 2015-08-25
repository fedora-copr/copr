# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint
from coprs.exceptions import InsufficientRightsException
from coprs.rest_api.exceptions import AccessForbidden
from coprs.rest_api.resources.project import rest_api_auth_required
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one
from ... import db


class ProjectChrootListR(Resource):

    def get(self, project_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        return {
            "chroots": [
                {
                    "chroot": mm_serialize_one(CoprChrootSchema, chroot),
                    "_links": {
                        "project": {"href": url_for(".projectr", project_id=copr.id)},
                        "self": {"href": url_for(".projectchrootr",
                                                 project_id=project_id,
                                                 name=chroot.name)},
                    }
                } for chroot in copr.copr_chroots
            ],
            "_links": {
                "self": {"href": url_for(".projectchrootlistr", project_id=project_id)}
            }
        }


class ProjectChrootR(Resource):

    def get(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = CoprChrootsLogic.get_by_name_safe(copr, name)

        return {
            "chroot": mm_serialize_one(CoprChrootSchema, chroot),
            "_links": {
                "project": {"href": url_for(".projectr", project_id=copr.id)},
                "self": {"href": url_for(".projectchrootr",
                                         project_id=project_id,
                                         name=chroot.name)},
            }
        }

    @rest_api_auth_required
    def delete(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = CoprChrootsLogic.get_by_name_safe(copr, name)

        try:
            CoprChrootsLogic.remove_copr_chroot(flask.g.user, chroot)
        except InsufficientRightsException as err:
            raise AccessForbidden("Failed to remove copr chroot: {}".format(err))

        db.session.commit()

        return None, 204
