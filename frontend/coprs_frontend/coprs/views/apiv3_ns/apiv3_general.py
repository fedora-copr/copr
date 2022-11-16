import os
import re

import flask

from coprs import app, oid, db
from coprs.views.apiv3_ns import apiv3_ns
from coprs.exceptions import AccessRestricted
from coprs.views.misc import api_login_required
from coprs.auth import UserAuth


def auth_check_response():
    """
    Used in misc and apiv3 for returning info about the user.
    """
    return flask.g.user.to_dict()


def gssapi_login_action():
    """
    Redirect the successful log-in attempt, or return the JSON data that user
    expects.
    """
    if "web-ui" in flask.request.full_path:
        flask.flash("Welcome, {0}".format(flask.g.user.name), "success")
        return flask.redirect(oid.get_next_url())
    return flask.jsonify(auth_check_response())


def krb_straighten_username(krb_remote_user):
    """
    Cleanup the user's principal, and return just simple username.  Remove
    disallowed characters for the service principals.
    """
    # Input should look like 'USERNAME@REALM.TLD', strip realm.
    username = re.sub(r'@.*', '', krb_remote_user)

    # But USERNAME part can consist of USER/DOMAIN.TLD.
    # TODO: Do we need more clever thing here?
    username = re.sub('/', '_', username)

    # Based on restrictions for project name: "letters, digits, underscores,
    # dashes and dots", it is worth limitting the username here, too.
    # TODO: Store this pattern on one place.
    return username if re.match(r"^[\w.-]+$", username) else None


@apiv3_ns.route("/")
def home():
    return flask.jsonify({"version": 3})


@apiv3_ns.route("/auth-check")
@api_login_required
def auth_check():
    return flask.jsonify(auth_check_response())


def auth_403(message):
    """
    Return appropriately formatted GSSAPI 403 error for both web-ui and API
    """
    message = "Can't log-in using GSSAPI: " + message
    raise AccessRestricted(message)


@apiv3_ns.route("/gssapi_login/", methods=["GET"])
@apiv3_ns.route("/gssapi_login/web-ui/", methods=["GET"])
def gssapi_login():
    """
    Log-in using the GSSAPI/Kerberos credentials

    Note that if we are able to get here, either the user is authenticated
    correctly, or apache is mis-configured and it does not perform KRB
    authentication at all (REMOTE_USER wouldn't be set, see below).
    """

    # Already logged in?
    if flask.g.user is not None:
        return gssapi_login_action()

    if app.config["DEBUG"] and 'TEST_REMOTE_USER' in os.environ:
        # For local testing (without krb5 keytab and other configuration)
        flask.request.environ['REMOTE_USER'] = os.environ['TEST_REMOTE_USER']

    if 'REMOTE_USER' not in flask.request.environ:
        nocred = "Kerberos authentication failed (no credentials provided)"
        return auth_403(nocred)

    krb_username = flask.request.environ['REMOTE_USER']
    app.logger.debug("krb5 login attempt: " + krb_username)
    username = krb_straighten_username(krb_username)
    if not username:
        return auth_403("invalid krb5 username: " + krb_username)

    user = UserAuth.user_object(username=username)
    db.session.add(user)
    db.session.commit()

    flask.g.user = user
    flask.session['krb5_login'] = user.name
    app.logger.info(
        "%s '%s' logged in",
        "Admin" if user.admin else "User",
        user.name
    )
    return gssapi_login_action()
