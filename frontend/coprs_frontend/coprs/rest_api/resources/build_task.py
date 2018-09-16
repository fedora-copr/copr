# coding: utf-8

from flask import url_for
from flask_restful import Resource
from flask_restful import Resource, reqparse
from flask_restful.reqparse import Argument

from marshmallow import pprint
from marshmallow import Schema, fields
from marshmallow import Schema, fields, validates_schema, ValidationError, validate

from copr_common.enums import StatusEnum
from coprs.rest_api.common import render_build_task
from ...exceptions import MalformedArgumentException
from ...logic.builds_logic import BuildsLogic, BuildChrootsLogic
from ..exceptions import MalformedRequest
from ..util import get_one_safe, get_request_parser


# todo: add redirect from /build_tasks/<int:build_id> -> /build_tasks?build_id=<build_id>
# class BuildTaskListRedirectBuildIdR(Resource):
#     def get(self, build_id):
#         resp = make_response("", 302)
#         resp.headers["Location"] ==  url_for(".buildtasklistr", build_id=build_id)


class BuildTaskListR(Resource):
    state_choices = StatusEnum.vals.keys()

    def get(self):

        parser = get_request_parser()

        parser.add_argument('owner', type=str,)
        parser.add_argument('project_id', type=int)
        parser.add_argument('build_id', type=int)
        parser.add_argument('group', type=str)

        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        parser.add_argument(
            'state', type=str, choices=self.state_choices,
            help=u"allowed states: {}".format(" ".join(self.state_choices)))

        req_args = parser.parse_args()

        self_params = dict(req_args)

        query = BuildChrootsLogic.get_multiply()
        if self_params.get("build_id") is not None:
            query = BuildChrootsLogic.filter_by_build_id(
                query, self_params["build_id"])
        elif self_params.get("project_id") is not None:
            query = BuildChrootsLogic.filter_by_project_id(
                query, self_params["project_id"])
        elif self_params.get("owner") is not None:
            query = BuildChrootsLogic.filter_by_project_user_name(
                query, self_params["owner"])
        elif self_params.get("group") is not None:
            query = BuildChrootsLogic.filter_by_group_name(query, req_args["group"])

        state = self_params.get("state")
        if state:
            query = BuildChrootsLogic.filter_by_state(query, state)

        if req_args["limit"] is not None:
            limit = req_args["limit"]
            if limit <= 0 or limit > 100:
                limit = 100
        else:
            limit = 100
        self_params["limit"] = limit
        query = query.limit(limit)

        if "offset" in self_params is not None:
            query = query.offset(self_params["offset"])

        build_chroots = query.all()
        return {
            "build_tasks": [
                render_build_task(chroot)
                for chroot in build_chroots
            ],
            "_links": {
                "self": {"href": url_for(".buildtasklistr", **self_params)}
            }
        }


class BuildTaskR(Resource):

    @staticmethod
    def _get_chroot_safe(build_id, name):
        try:
            chroot = get_one_safe(
                BuildChrootsLogic.get_by_build_id_and_name(build_id, name),
                "Build task {} for build {} not found"
            )
        except MalformedArgumentException as err:
            raise MalformedRequest("Bad mock chroot name: {}".format(err))
        return chroot

    def get(self, build_id, name):
        chroot = self._get_chroot_safe(build_id, name)
        return render_build_task(chroot)

    # todo: add put method: allows only to pass status: cancelled to cancel build

