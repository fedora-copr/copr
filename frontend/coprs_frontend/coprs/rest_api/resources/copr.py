import base64
import datetime
import functools

import flask
from flask import url_for
from flask_restful import Resource, reqparse
from marshmallow import pprint

from coprs import db
from coprs.exceptions import DuplicateException
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.exceptions import ActionInProgressException, InsufficientRightsException
from .build import BuildListR
# from .chroot import CoprChrootListR, CoprChrootR
from coprs.rest_api.schemas import CoprSchema
from ..exceptions import ObjectAlreadyExists, AuthFailed
from ..util import get_one_safe, json_loads_safe, mm_deserialize, render_allowed_method


def rest_api_auth_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        apt_login = None
        if "Authorization" in flask.request.headers:
            base64string = flask.request.headers["Authorization"]
            base64string = base64string.split()[1].strip()
            userstring = base64.b64decode(base64string)
            (apt_login, token) = userstring.split(":")
        token_auth = False
        if token and apt_login:
            user = UsersLogic.get_by_api_login(apt_login).first()
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


class CoprListR(Resource):

    @rest_api_auth_required
    def post(self):
        """
        Creates new copr
        """
        owner = flask.g.user

        result = mm_deserialize(CoprSchema(), flask.request.data)
        # todo check that chroots are available
        pprint(result.data)
        try:
            CoprsLogic.add(user=owner, check_for_duplicates=True, **result.data)
            db.session.commit()
        except DuplicateException as error:
            raise ObjectAlreadyExists(data=error)

        return "New copr was created", 201

    def get(self):
        """
        Get coprs collection
        :return:
        """
        parser = reqparse.RequestParser()
        parser.add_argument('owner', dest='username', type=str)
        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)
        # parser.add_argument('help', type=bool)
        req_args = parser.parse_args()

        kwargs = {}
        for key in ["username"]:
            if req_args[key]:
                kwargs[key] = req_args[key]

        if "username" in kwargs:
            query = CoprsLogic.get_multiple_owned_by_username(req_args["username"])
        else:
            query = CoprsLogic.get_multiple(flask.g.user)

        # todo: also could be optional
        query = CoprsLogic.join_builds(query)

        if "limit" in req_args:
            query = query.offset(req_args["offset"])

        # todo: add maximum allowed limit and also use as a default limit
        if req_args["limit"]:
            query = query.limit(req_args["limit"])

        coprs_list = query.all()

        result_dict = {
            "_links": {
                "self": {"href": url_for(".coprlistr", **req_args)}
            },
            "coprs": [
                {
                    "copr": CoprSchema().dump(copr)[0],
                    "_links": {
                        "self": {"href": url_for(".coprr", copr_id=copr.id)}
                    },
                }
                for copr in coprs_list
            ],

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


class CoprR(Resource):

    @rest_api_auth_required
    def delete(self, copr_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(copr_id)))

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

    def get(self, copr_id):
        # parser = reqparse.RequestParser()
        # parser.add_argument('show_builds', type=bool, default=True)
        # parser.add_argument('show_chroots', type=bool, default=True)
        # req_args = parser.parse_args()

        copr = get_one_safe(CoprsLogic.get_by_id(int(copr_id)))

        return {
            "copr": CoprSchema().dump(copr)[0],
            "_links": {
                "self": {"href": url_for(".coprr", copr_id=copr.id)},
                #"chroots": bp_url_for(ChrootListR.endpoint,
                #                      )
                "builds": {"href": url_for(".buildlistr", owner=copr.owner.name, project=copr.name)}
            },
            # "allowed_methods": [
            #     render_allowed_method("GET", "Get single copr", require_auth=False),
            #     render_allowed_method("DELETE", "Delete current copr", require_auth=True),
            # ]
        }

    @rest_api_auth_required
    def put(self, copr_id):
        """
        Modifies project by replacment of provided fields
        """
        pass

