# coding: utf-8

import flask

# from flask_restful_swagger import swagger

from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic

from coprs.rest_api.schemas import BuildSchema

from coprs.rest_api.util import get_one_safe, bp_url_for

from flask_restful import Resource, reqparse


class BuildListR(Resource):

    def get(self):

        parser = reqparse.RequestParser()

        parser.add_argument('owner', type=str,)
        parser.add_argument('project', type=str)

        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        req_args = parser.parse_args()

        if "owner" and "project" in req_args:
            query = BuildsLogic.get_multiple_by_name(
                req_args["owner"], req_args["project"])
        else:
            query = BuildsLogic.get_multiple()

        if "limit" in req_args:
            limit = req_args["limit"]
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
                    "link": bp_url_for(BuildR.endpoint, build_id=build.id),
                } for build in builds
            ],
            "links": {
                "self": bp_url_for(BuildListR.endpoint, **req_args),
            },
        }


# @swagger.model
# class BuildItem(object):
#     def __init__(self, build_id):
#         pass


class BuildR(Resource):

    def get(self, build_id):
        """
        Get single build by id
        """
        build = get_one_safe(BuildsLogic.get(build_id),
                             "Not found build with id: {}".format(build_id))
        return {
            "build": BuildSchema().dump(build)[0],
            "links": {
                "self": bp_url_for(BuildR.endpoint, build_id=build_id),
                # TODO: can't do this due to circular imports
                # "parent_copr": url_for(CoprR.endpoint,
                #                        owner=build.copr.owner.name,
                #                        project=build.copr.name),
            }
        }




