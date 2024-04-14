# pylint: disable=missing-class-docstring

from http import HTTPStatus

import flask

from flask_restx import Namespace, Resource

from coprs.views.apiv3_ns import api, editable_copr, get_copr, deprecated_route_method_type
from coprs.views.misc import api_login_required
from coprs.exceptions import ObjectNotFound, BadRequest
from coprs.helpers import PermissionEnum
from coprs.logic.coprs_logic import CoprPermissionsLogic
from coprs.logic.users_logic import UsersLogic
from coprs.mail import send_mail, PermissionRequestMessage, PermissionChangeMessage
from coprs.views.apiv3_ns.schema.schemas import can_build_params, can_build_in_model, fullname_params
from coprs import db_session_scope, models


apiv3_permissions_ns = Namespace("permissions", path="/project/permissions", description="Permissions")
api.add_namespace(apiv3_permissions_ns)


@apiv3_permissions_ns.route("/can_build_in/<who>/<ownername>/<projectname>")
class CanBuild(Resource):
    @apiv3_permissions_ns.doc(params=can_build_params)
    @apiv3_permissions_ns.marshal_with(can_build_in_model)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    def get(self, who, ownername, projectname):
        """
        Can user submit builds in the project?
        Can a user `who` submit builds in the `ownername/projectname` project?
        """
        user = UsersLogic.get(who).one()
        copr = get_copr(ownername, projectname)
        result = {
            "who": user.name,
            "ownername": copr.owner.name,
            "projectname": copr.name,
            "can_build_in": user.can_build_in(copr),
        }
        return result


@apiv3_permissions_ns.route("/get/<ownername>/<projectname>")
class GetPermissions(Resource):
    @api_login_required
    @editable_copr
    @apiv3_permissions_ns.doc(params=fullname_params)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    @apiv3_permissions_ns.response(
        HTTPStatus.NOT_FOUND.value, HTTPStatus.NOT_FOUND.description
    )
    def get(self, copr):
        """
        Get permissions for the project
        Get permission for the `ownername/projectname` project.
        """
        if not copr.copr_permissions:
            raise ObjectNotFound(
                "No permissions set on {0} project".format(copr.full_name))

        permissions = {}
        for perm in copr.copr_permissions:
            permissions[perm.user.name] = {
                'admin': PermissionEnum(perm.copr_admin),
                'builder': PermissionEnum(perm.copr_builder),
            }

        return {'permissions': permissions}


@apiv3_permissions_ns.route("/set/<ownername>/<projectname>")
class SetPermissions(Resource):
    @staticmethod
    def _common(copr):
        permissions = flask.request.get_json()
        if not isinstance(permissions, dict):
            raise BadRequest(
                "request is not a dictionary, expected format: "
                "{'username': {'admin': 'nothing', 'builder': 'request'} ...}")

        if not permissions:
            raise BadRequest("no permission change requested")

        updated = {}
        messages = []
        with db_session_scope():
            for username, perm_set in permissions.items():
                user = models.User.query.filter_by(username=username).first()
                if not user:
                    raise BadRequest("user '{0}' doesn't exist in database".format(
                        username))

                permission_dict = {}
                for perm, state in perm_set.items():
                    change = CoprPermissionsLogic.set_permissions(
                        flask.g.user, copr, user, perm, state)
                    if change:
                        updated[username] = True
                        permission_dict['old_' + perm] = change[0]
                        permission_dict['new_' + perm] = change[1]

                if permission_dict:
                    msg = PermissionChangeMessage(copr, permission_dict)
                    messages.append({'address': user.mail, 'message': msg})

        # send emails only if transaction succeeded
        for task in messages:
            if flask.current_app.config.get("SEND_EMAILS", False):
                send_mail([task['address']], task['message'])

        return {'updated': list(updated.keys())}

    @api_login_required
    @editable_copr
    @apiv3_permissions_ns.doc(params=fullname_params)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    @apiv3_permissions_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, copr):
        """
        Create permissions for the project
        Create permission for the `ownername/projectname` project.
        """
        return self._common(copr)

    @api_login_required
    @editable_copr
    @apiv3_permissions_ns.doc(params=fullname_params)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    @apiv3_permissions_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def put(self, copr):
        """
        Change permissions for the project
        Change permission for the `ownername/projectname` project.
        """
        return self._common(copr)


@apiv3_permissions_ns.route("/request/<ownername>/<projectname>")
class RequestPermission(Resource):
    @staticmethod
    def _common(ownername, projectname):
        copr = get_copr(ownername, projectname)
        roles = flask.request.get_json()
        if not isinstance(roles, dict):
            raise BadRequest("invalid 'roles' dict format, expected: "
                             "{'admin': True, 'builder': False}")
        if not roles:
            raise BadRequest("no permission requested")

        permission_dict = {}
        with db_session_scope():
            for permission, request_bool in roles.items():
                change = CoprPermissionsLogic.request_permission(
                    copr, flask.g.user, permission, request_bool)
                if change:
                    permission_dict['old_' + permission] = change[0]
                    permission_dict['new_' + permission] = change[1]

        if permission_dict:
            msg = PermissionRequestMessage(copr, flask.g.user, permission_dict)
            for address in copr.admin_mails:
                if flask.current_app.config.get("SEND_EMAILS", False):
                    send_mail([address], msg)

        return {'updated': bool(permission_dict)}

    @deprecated_route_method_type(apiv3_permissions_ns, "POST", "PUT")
    @api_login_required
    @apiv3_permissions_ns.doc(params=fullname_params)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    @apiv3_permissions_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, ownername, projectname):
        """
        Request permissions for the project
        Request permissions (admin, builder, ...) for the `ownername/projectname` project.
        """
        return self._common(ownername, projectname)

    @api_login_required
    @apiv3_permissions_ns.doc(params=fullname_params)
    @apiv3_permissions_ns.response(HTTPStatus.OK.value, HTTPStatus.OK.description)
    @apiv3_permissions_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def put(self, ownername, projectname):
        """
        Request permissions for the project
        Request permissions (admin, builder, ...) for the `ownername/projectname` project.
        """
        return self._common(ownername, projectname)
