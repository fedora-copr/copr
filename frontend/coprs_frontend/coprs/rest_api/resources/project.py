from logging import getLogger

log = getLogger(__name__)

import flask
from flask import url_for, make_response
from flask_restful import Resource, reqparse

from ... import db
from ...logic.builds_logic import BuildsLogic
from ...logic.complex_logic import ComplexLogic
from ...logic.helpers import slice_query
from ...logic.coprs_logic import CoprsLogic
from ...exceptions import ActionInProgressException, InsufficientRightsException

from ...exceptions import DuplicateException

from ..common import rest_api_auth_required, render_copr_chroot, render_build, render_project
from ..schemas import ProjectSchema, ProjectCreateSchema
from ..exceptions import ObjectAlreadyExists, CannotProcessRequest, AccessForbidden
from ..util import get_one_safe, mm_deserialize


class ProjectListR(Resource):

    @rest_api_auth_required
    def post(self):
        """
        Creates new copr
        """
        owner = flask.g.user
        result = mm_deserialize(ProjectCreateSchema(), flask.request.data)

        req = result.data
        name = req.pop("name")
        selected_chroots = req.pop("chroots")

        try:
            project = CoprsLogic.add(
                user=owner, check_for_duplicates=True,
                name=name,
                selected_chroots=selected_chroots,
                **req
            )
            db.session.commit()
        except DuplicateException as error:
            raise ObjectAlreadyExists(data=error)

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".projectr", project_id=project.id)
        return resp

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('owner', dest='username', type=str)
        parser.add_argument('name', dest='name', type=str)
        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        # parser.add_argument('help', type=bool)
        req_args = parser.parse_args()

        if req_args["username"]:
            query = CoprsLogic.get_multiple_owned_by_username(req_args["username"])
        else:
            query = CoprsLogic.get_multiple(flask.g.user)

        if req_args["name"]:
            query = CoprsLogic.filter_by_name(query, req_args["name"])

        # todo: add maximum allowed limit and also use as a default limit
        limit = 100
        offset = 0
        if req_args["limit"]:
            limit = req_args["limit"]
        if req_args["offset"]:
            offset = req_args["offset"]

        query = slice_query(query, limit, offset)
        coprs_list = query.all()

        result_dict = {
            "_links": {
                "self": {"href": url_for(".projectlistr", **req_args)}
            },
            "coprs": [render_project(copr) for copr in coprs_list],
        }

        return result_dict


class ProjectR(Resource):

    @rest_api_auth_required
    def delete(self, project_id):
        project = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        try:
            ComplexLogic.delete_copr(project)
            db.session.commit()
        except ActionInProgressException as err:
            raise CannotProcessRequest(str(err))
        except InsufficientRightsException as err:
            raise AccessForbidden(str(err))

        return None, 204

    def get(self, project_id):
        parser = reqparse.RequestParser()
        parser.add_argument('show_builds', type=bool, default=False)
        parser.add_argument('show_chroots', type=bool, default=False)
        req_args = parser.parse_args()

        project = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        self_params = {}
        if req_args["show_builds"]:
            self_params["show_builds"] = req_args["show_builds"]
        if req_args["show_chroots"]:
            self_params["show_chroots"] = req_args["show_chroots"]

        answer = render_project(project, self_params)

        if req_args["show_builds"]:
            answer["project_builds"] = [
                render_build(build)
                for build in BuildsLogic.get_multiple_by_copr(project).all()
            ]

        if req_args["show_chroots"]:
            answer["project_chroots"] = [
                render_copr_chroot(chroot)
                for chroot in project.copr_chroots
            ]

        return answer

    @rest_api_auth_required
    def put(self, project_id):
        """
        Modifies project by replacement of provided fields
        """
        project = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        project_dict = mm_deserialize(ProjectSchema(), flask.request.data).data
        # pprint(project_dict)

        for k, v in project_dict.items():
            setattr(project, k, v)

        try:
            CoprsLogic.update(flask.g.user, project)
            db.session.commit()
        except InsufficientRightsException as err:
            raise AccessForbidden(str(err))

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".projectr", project_id=project.id)
        return resp

