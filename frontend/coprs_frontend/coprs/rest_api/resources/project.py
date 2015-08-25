import base64
import datetime
import functools
from logging import getLogger
log = getLogger(__name__)

import flask
from flask import url_for
from flask_restful import Resource, reqparse
from marshmallow import pprint

from coprs import db
from coprs.exceptions import DuplicateException
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.helpers import slice_query
from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.exceptions import ActionInProgressException, InsufficientRightsException
from .build import BuildListR
# from .chroot import CoprChrootListR, CoprChrootR
from coprs.rest_api.schemas import ProjectSchema
from ..exceptions import ObjectAlreadyExists, AuthFailed
from ..util import get_one_safe, json_loads_safe, mm_deserialize, render_allowed_method, mm_serialize_one


def rest_api_auth_required(f):
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


def render_project(copr):
    return {
        "copr": mm_serialize_one(ProjectSchema, copr),
        "_links": {
            "self": {"href": url_for(".projectr", project_id=copr.id)},
            "builds": {"href": url_for(".buildlistr", project_id=copr.id)},
            "chroots": {"href": url_for(".projectchrootlistr", project_id=copr.id)}
        },
        # "allowed_methods": [
        #     render_allowed_method("GET", "Get single copr", require_auth=False),
        #     render_allowed_method("DELETE", "Delete current copr", require_auth=True),
        # ]
    }


class ProjectListR(Resource):

    @rest_api_auth_required
    def post(self):
        """
        Creates new copr
        """
        owner = flask.g.user

        result = mm_deserialize(ProjectSchema(), flask.request.data)
        if result.errors:
            return "Failed to parse request", 400

        # todo check that chroots are available
        req = result.data

        extra = {
            k: req[k]
            for k in [
                "description",
                "instructions",
                "contact",
                "homepage",
                "auto_createrepo",
                "build_enable_net",
                "repos"
            ] if k in req
        }

        try:
            copr = CoprsLogic.add(
                user=owner, check_for_duplicates=True,
                name=req["name"],
                selected_chroots=req["chroots"],
                **extra
            )
            db.session.commit()
        except DuplicateException as error:
            raise ObjectAlreadyExists(data=error)

        return render_project(copr), 201

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

        # TODO: show only if user provided ?help=true param
        #
        # if req_args.get("help"):
        #     result_dict["allowed_methods"] = [
        #         render_allowed_method("GET", "Get list of coprs", require_auth=False,
        #                               params=[
        #                                   "username: filter coprs owned by the user",
        #                                   "limit: show only the given number of coprs",
        #                                   "offset: skip given number of coprs",
        #                               ]),
        #         render_allowed_method("POST", "Creates new copr, send dict with copr fields"),
        #     ]

        return result_dict


class ProjectR(Resource):

    @rest_api_auth_required
    def delete(self, project_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        raise NotImplementedError()

        try:
            ComplexLogic.delete_copr(copr)
        except (ActionInProgressException,
                InsufficientRightsException) as err:
            db.session.rollback()
            raise
        else:
            db.session.commit()

        return None, 204

    def get(self, project_id):
        # parser = reqparse.RequestParser()
        # parser.add_argument('show_builds', type=bool, default=True)
        # parser.add_argument('show_chroots', type=bool, default=True)
        # req_args = parser.parse_args()

        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        return render_project(copr)

    @rest_api_auth_required
    def put(self, project_id):
        """
        Modifies project by replacment of provided fields
        """
        pass

