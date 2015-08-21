# coding: utf-8

import flask
from flask import url_for

# from flask_restful_swagger import swagger

from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.users_logic import UsersLogic

from coprs.rest_api.schemas import BuildSchema

from coprs.rest_api.util import get_one_safe

from flask_restful import Resource, reqparse


class BuildListR(Resource):

    def get(self):

        parser = reqparse.RequestParser()

        parser.add_argument('owner', type=str,)
        parser.add_argument('copr_id', type=int)

        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        req_args = parser.parse_args()

        if req_args["copr_id"] is not None:
            copr = get_one_safe(CoprsLogic.get_by_id(req_args["copr_id"]))
            query = BuildsLogic.get_multiple_by_copr(copr)
        elif req_args["owner" ] is not None:
            user = get_one_safe(UsersLogic.get(req_args["owner"]))
            query = BuildsLogic.get_multiple_by_owner(user)
        else:
            query = BuildsLogic.get_multiple()

        if "limit" in req_args:
            limit = req_args["limit"]
            if limit <= 0 or limit > 100:
                limit = 100
        else:
            limit = 100

        query = query.limit(limit)

        if "offset" in req_args:
            query = query.offset(req_args["offset"])

        builds = query.all()
        return {

            "builds": [
                {
                    "build": BuildSchema().dump(build)[0],
                    "_links": {
                        "self": {"href": url_for(".buildr", build_id=build.id)},
                    }
                } for build in builds
            ],
            "_links": {
                "self": {"href": url_for(".buildlistr", **req_args)},
            },
        }


class BuildR(Resource):

    def get(self, build_id):
        """
        Get single build by id
        """
        build = get_one_safe(BuildsLogic.get(build_id),
                             "Not found build with id: {}".format(build_id))

        return {
            "build": BuildSchema().dump(build)[0],
            "_links": {
                "self": url_for(".buildr", build_id=build_id),
                "parent_copr": url_for(".coprr", copr_id=build.id),
            }
        }


# to get build details and cancel individual build chroots
# class BuildChrootR(Resource):
#     def get(self, owner, project, name):
#         copr = get_one_safe(CoprsLogic.get(flask.g.user, owner, project),
#                            "Copr {}/{} not found".format(owner, project))
#         chroot = get_one_safe(CoprChrootsLogic.get(copr, name))
#
#         return {
#             "chroot": chroot.to_dict(),
#             "links": {
#                 "self": bp_url_for(BuildChrootR.endpoint, owner=owner, project=project, name=name)
#             }
#         }

