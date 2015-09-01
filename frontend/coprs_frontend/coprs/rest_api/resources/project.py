import base64
import datetime
import functools
from logging import getLogger
from coprs.logic.builds_logic import BuildsLogic
from coprs.rest_api.resources.common import render_copr_chroot, render_build

log = getLogger(__name__)

import flask
from flask import url_for, make_response
from flask_restful import Resource, reqparse
from marshmallow import pprint

from coprs import db
from coprs.exceptions import DuplicateException
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.helpers import slice_query
from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.exceptions import ActionInProgressException, InsufficientRightsException
from coprs.rest_api.schemas import ProjectSchema, ProjectCreateSchema
from ..exceptions import ObjectAlreadyExists, AuthFailed, CannotProcessRequest, AccessForbidden
from ..util import get_one_safe, json_loads_safe, mm_deserialize, render_allowed_method, mm_serialize_one


def rest_api_auth_required(f):
    # todo: move to common.py and test this
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        api_login = None
        try:
            if "Authorization" in flask.request.headers:
                base64string = flask.request.headers["Authorization"]
                base64string = base64string.split()[1].strip()
                userstring = base64.b64decode(base64string)
                (api_login, token) = userstring.split(":")
        except Exception:
            log.exception("Failed to get auth token from headers")
            api_login = token = None

        token_auth = False
        if token and api_login:
            user = UsersLogic.get_by_api_login(api_login).first()
            if (user and user.api_token == token and
                    user.api_token_expiration >= datetime.date.today()):

                token_auth = True
                flask.g.user = user
        if not token_auth:
            message = (
                "Login invalid/expired. "
                "Please visit https://copr.fedoraproject.org/api "
                "get or renew your API token.")

            raise AuthFailed(message)
        return f(*args, **kwargs)
    return decorated_function


def render_project(copr, self_params=None):
    if self_params is None:
        self_params = {}

    return {
        "project": mm_serialize_one(ProjectSchema, copr),
        "_links": {
            "self": {"href": url_for(".projectr", project_id=copr.id, **self_params)},
            "builds": {"href": url_for(".buildlistr", project_id=copr.id)},
            "chroots": {"href": url_for(".projectchrootlistr", project_id=copr.id)}
        },
    }


class ProjectListR(Resource):

    @rest_api_auth_required
    def post(self):
        """
        Creates new copr
        """
        owner = flask.g.user

        result = mm_deserialize(ProjectCreateSchema(), flask.request.data)

        # todo check that chroots are available
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

