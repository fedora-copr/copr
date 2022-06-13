import flask
from flask import url_for, make_response
from flask_restful import Resource

from ... import db
from ...logic.builds_logic import BuildsLogic
from ...logic.complex_logic import ComplexLogic
from ...logic.helpers import slice_query
from ...logic.coprs_logic import CoprsLogic
from ...exceptions import ActionInProgressException, InsufficientRightsException

from ...exceptions import DuplicateException

from ..common import rest_api_auth_required, render_copr_chroot, render_build, render_project, get_project_safe
from ..schemas import ProjectSchema, ProjectCreateSchema
from ..exceptions import ObjectAlreadyExists, CannotProcessRequest, AccessForbidden
from ..util import mm_deserialize, get_request_parser, arg_bool


class ProjectListR(Resource):

    @rest_api_auth_required
    def post(self):
        """
        Creates new copr
        """
        user = flask.g.user
        req = mm_deserialize(ProjectCreateSchema(), flask.request.data.decode("utf-8"))
        name = req.pop("name")

        selected_chroots = req.pop("chroots", None)

        group_name = req.pop("group", None)
        if group_name:
            group = ComplexLogic.get_group_by_name_safe(group_name)
        else:
            group = None

        try:
            project = CoprsLogic.add(
                user=user, check_for_duplicates=True,
                name=name,
                selected_chroots=selected_chroots,
                group=group,
                **req
            )

            db.session.commit()
        except DuplicateException as error:
            raise ObjectAlreadyExists(msg=str(error))

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".projectr", project_id=project.id)
        return resp

    def get(self):
        parser = get_request_parser()
        parser.add_argument('owner', type=str)
        parser.add_argument('group', type=str)
        parser.add_argument('name', type=str)
        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)
        parser.add_argument('search_query', type=str)

        req_args = parser.parse_args()

        if req_args["search_query"]:
            ownername = req_args["owner"]
            if req_args["group"]:
                ownername = "@" + req_args["group"]

            query = CoprsLogic.get_multiple_fulltext(
                req_args["search_query"],
                projectname=req_args["name"],
                ownername=ownername)

        else:
            query = CoprsLogic.get_multiple(flask.g.user)
            if req_args["owner"]:
                query = CoprsLogic.filter_by_user_name(query, req_args["owner"])

            if req_args["group"]:
                query = CoprsLogic.filter_by_group_name(query, req_args["group"])

            if req_args["name"]:
                query = CoprsLogic.filter_by_name(query, req_args["name"])

        query = CoprsLogic.set_query_order(query)

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
            "projects": [render_project(copr) for copr in coprs_list],
        }

        return result_dict


class ProjectR(Resource):

    @rest_api_auth_required
    def delete(self, project_id):
        project = get_project_safe(project_id)

        try:
            ComplexLogic.delete_copr(project)
            db.session.commit()
        except ActionInProgressException as err:
            raise CannotProcessRequest(str(err))
        except InsufficientRightsException as err:
            raise AccessForbidden(str(err))

        return None, 204

    def get(self, project_id):
        parser = get_request_parser()
        parser.add_argument('show_builds', type=arg_bool, default=False)
        parser.add_argument('show_chroots', type=arg_bool, default=False)
        req_args = parser.parse_args()

        project = get_project_safe(project_id)
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
                for chroot in project.active_copr_chroots
            ]

        return answer

    @rest_api_auth_required
    def put(self, project_id):
        """
        Modifies project by replacement of provided fields
        """
        project = get_project_safe(project_id)

        project_dict = mm_deserialize(ProjectSchema(), flask.request.data.decode("utf-8"))

        for k, v in project_dict.items():
            setattr(project, k, v)

        try:
            CoprsLogic.update(flask.g.user, project)
            db.session.commit()
        except InsufficientRightsException as err:
            raise AccessForbidden(str(err))

        return "", 204

