# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one


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
