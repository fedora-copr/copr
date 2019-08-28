import flask

from coprs.views.apiv3_ns import apiv3_ns
from coprs.views.misc import api_login_required
from coprs.exceptions import ObjectNotFound, BadRequest
from coprs.helpers import PermissionEnum
from coprs.logic.coprs_logic import CoprPermissionsLogic
from coprs.mail import send_mail, PermissionRequestMessage, PermissionChangeMessage
from coprs import db_session_scope, models

from . import GET, PUT, editable_copr, get_copr


@apiv3_ns.route("/project/permissions/get/<ownername>/<projectname>", methods=GET)
@api_login_required
@editable_copr
def get_permissions(copr):
    if not copr.copr_permissions:
        raise ObjectNotFound(
            "No permissions set on {0} project".format(copr.full_name))

    permissions = {}
    for perm in copr.copr_permissions:
        permissions[perm.user.name] = {
            'admin': PermissionEnum(perm.copr_admin),
            'builder': PermissionEnum(perm.copr_builder),
        }

    return flask.jsonify({'permissions': permissions})


@apiv3_ns.route("/project/permissions/set/<ownername>/<projectname>", methods=PUT)
@api_login_required
@editable_copr
def set_permissions(copr):
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
                    permission_dict['old_'+perm] = change[0]
                    permission_dict['new_'+perm] = change[1]

            if permission_dict:
                msg = PermissionChangeMessage(copr, permission_dict)
                messages.append({'address': user.mail, 'message': msg})

    # send emails only if transaction succeeded
    for task in messages:
        if flask.current_app.config.get("SEND_EMAILS", False):
            send_mail([task['address']], task['message'])

    return flask.jsonify({'updated': list(updated.keys())})


@apiv3_ns.route("/project/permissions/request/<ownername>/<projectname>", methods=PUT)
@api_login_required
def request_permissions(ownername, projectname):
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
                permission_dict['old_'+permission] = change[0]
                permission_dict['new_'+permission] = change[1]

    if permission_dict:
        msg = PermissionRequestMessage(copr, flask.g.user, permission_dict)
        for address in copr.admin_mails:
            if flask.current_app.config.get("SEND_EMAILS", False):
                send_mail([address], msg)

    return flask.jsonify({'updated': bool(permission_dict)})
