# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint
from coprs.logic.builds_logic import BuildsLogic
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema, BuildChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one


class BuildChrootListR(Resource):
    def get(self, build_id):
        build = get_one_safe(BuildsLogic.get(build_id),
                             "Not found build with id: {}".format(build_id))

        return {
            "chroots": [
                {
                    "chroot": mm_serialize_one(BuildChrootSchema, chroot),
                    "_links": {
                        "project": {"href": url_for(".projectr", project_id=build.copr_id)},
                        "self": {"href": url_for(".buildchrootr",
                                                 build_id=build.id,
                                                 name=chroot.name)},
                    }
                } for chroot in build.build_chroots
                ],
            "_links": {
                "self": {"href": url_for(".buildchrootlistr", build_id=build_id)}
            }
        }


class BuildChrootR(Resource):
    pass
    # def get(self, project_id, name):
    #     copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
    #     chroot = CoprChrootsLogic.get_by_name_safe(copr, name)
    #
    #     return {
    #         "chroot": mm_serialize_one(CoprChrootSchema, chroot),
    #         "_links": {
    #             "project": {"href": url_for(".projectr", project_id=copr.id)},
    #             "self": {"href": url_for(".projectchrootr",
    #                                      project_id=project_id,
    #                                      name=chroot.name)},
    #         }
    #     }
