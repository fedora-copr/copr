import base64
import datetime
import functools
from functools import wraps
import flask

from flask import send_file

from copr_common.enums import RoleEnum
from coprs import app
from coprs import db
from coprs import helpers
from coprs import models
from coprs import oid
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic
from coprs.exceptions import ObjectNotFound
from coprs.measure import checkpoint_start
from coprs.auth import FedoraAccounts, UserAuth


@app.before_request
def before_request():
    """
    Configure some useful defaults for (before) each request.
    """

    # Checkpoints initialization
    checkpoint_start()

    # Load the logged-in user, if any.
    # https://github.com/PyCQA/pylint/issues/3793
    # pylint: disable=assigning-non-slot
    flask.g.user = username = None

    username = UserAuth.current_username()
    if username:
        flask.g.user = models.User.query.filter(
            models.User.username == username).first()


misc = flask.Blueprint("misc", __name__)


def workaround_ipsilon_email_login_bug_handler(f):
    """
    We are working around an ipislon issue when people log in with their email,
    ipsilon then yields incorrect openid.identity:

      ERROR:root:Discovery verification failure for http://foo@fedoraproject.org.id.fedoraproject.org/

    The error above raises an exception in python-openid thus restarting the login process
    which turns into an infinite loop of requests. Since we drop the openid_error key from flask.session,
    we'll prevent the infinite loop to happen.

    Ref: https://pagure.io/ipsilon/issue/358
    """

    @functools.wraps(f)
    def _the_handler(*args, **kwargs):
        msg = flask.session.get("openid_error")
        if msg and "No matching endpoint found after discovering" in msg:
            # we need to advise to log out because the user will have an active FAS session
            # and the only way to break it is to log out
            logout_url = app.config["OPENID_PROVIDER_URL"] + "/logout"
            message = (
                    "You logged in using your email. <a href=\"https://pagure.io/ipsilon/issue/358\""
                    " target=\"_blank\">This is not supported.</a> "
                    "Please log in with your <em>FAS username</em> instead "
                    "<a href=\"%s\">after logging out here</a>." % logout_url
            )
            flask.session.pop("openid_error")
            flask.flash(message, "error")
            # do not redirect to "/login" since it's gonna be an infinite loop
            return flask.redirect("/")
        return f(*args, **kwargs)
    return _the_handler


@misc.route("/login/", methods=["GET"])
@workaround_ipsilon_email_login_bug_handler
@oid.loginhandler
def oid_login():
    """
    Entry-point for OpenID login
    """
    # After a successful FAS login, we are redirected to the `@oid.after_login`
    # function
    return FedoraAccounts.login()


@oid.after_login
def create_or_login(resp):
    flask.session["openid"] = resp.identity_url
    fasusername = FedoraAccounts.fed_raw_name(resp.identity_url)

    if not FedoraAccounts.is_user_allowed(fasusername):
        flask.flash("User '{0}' is not allowed".format(fasusername))
        return flask.redirect(oid.get_next_url())

    user = UserAuth.user_object(oid_resp=resp)
    db.session.add(user)
    db.session.commit()
    flask.flash(u"Welcome, {0}".format(user.name), "success")
    flask.g.user = user

    app.logger.info("%s '%s' logged in",
                    "Admin" if user.admin else "User",
                    user.name)

    if flask.request.url_root == oid.get_next_url():
        return flask.redirect(flask.url_for("coprs_ns.coprs_by_user",
                                            username=user.name))
    return flask.redirect(oid.get_next_url())


@misc.route("/logout/")
def logout():
    return UserAuth.logout()


def api_login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        api_login = None
        # flask.g.user can be already set in case a user is using gssapi auth,
        # in that case before_request was called and the user is known.
        if flask.g.user is not None:
            return f(*args, **kwargs)
        if "Authorization" in flask.request.headers:
            base64string = flask.request.headers["Authorization"]
            base64string = base64string.split()[1].strip()
            userstring = base64.b64decode(base64string)
            (api_login, token) = userstring.decode("utf-8").split(":")
        token_auth = False
        if token and api_login:
            user = UsersLogic.get_by_api_login(api_login).first()
            if (user and user.api_token == token and
                    user.api_token_expiration >= datetime.date.today()):
                token_auth = True
                flask.g.user = user
        if not token_auth:
            url = 'https://' + app.config["PUBLIC_COPR_HOSTNAME"]
            url = helpers.fix_protocol_for_frontend(url)

            msg = "Attempting to use invalid or expired API login '%s'"
            app.logger.info(msg, api_login)

            output = {
                "output": "notok",
                "error": "Login invalid/expired. Please visit {0}/api to get or renew your API token.".format(url),
            }
            jsonout = flask.jsonify(output)
            jsonout.status_code = 401
            return jsonout
        return f(*args, **kwargs)
    return decorated_function


def login_required(role=RoleEnum("user")):
    def view_wrapper(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if flask.g.user is None:
                return flask.redirect(flask.url_for("misc.oid_login",
                                                    next=flask.request.url))

            if role == RoleEnum("admin") and not flask.g.user.admin:
                flask.flash("You are not allowed to access admin section.")
                return flask.redirect(flask.url_for("coprs_ns.coprs_show"))

            return f(*args, **kwargs)
        return decorated_function
    # hack: if login_required is used without params, the "role" parameter
    # is in fact the decorated function, so we need to return
    # the wrapped function, not the wrapper
    # proper solution would be to use login_required() with parentheses
    # everywhere, even if they"re empty - TODO
    if callable(role):
        return view_wrapper(role)
    else:
        return view_wrapper


# backend authentication
def backend_authenticated(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth = flask.request.authorization
        if not auth or auth.password != app.config["BACKEND_PASSWORD"]:
            return "You have to provide the correct password\n", 401

        return f(*args, **kwargs)
    return decorated_function


def req_with_copr(f):
    @wraps(f)
    def wrapper(**kwargs):
        coprname = kwargs.pop("coprname")
        if "group_name" in kwargs:
            group_name = kwargs.pop("group_name")
            copr = ComplexLogic.get_group_copr_safe(group_name, coprname, with_mock_chroots=True)
        else:
            username = kwargs.pop("username")
            copr = ComplexLogic.get_copr_safe(username, coprname, with_mock_chroots=True)
        return f(copr, **kwargs)
    return wrapper


def req_with_copr_dir(f):
    @wraps(f)
    def wrapper(**kwargs):
        if "group_name" in kwargs:
            ownername = '@' + kwargs.pop("group_name")
        else:
            ownername = kwargs.pop("username")
        copr_dirname = kwargs.pop("copr_dirname")
        copr_dir = ComplexLogic.get_copr_dir_safe(ownername, copr_dirname)
        return f(copr_dir, **kwargs)
    return wrapper


def send_build_icon(build, no_cache=False):
    """
    Sends a build icon depending on the state of the build.
    We use cache depending on whether it was the last build of a package, where the status can
    change in a minute, or a specific build, where the status will not change.
    :param build: build whose state we are interested in.
    :param no_cache: whether we want to cache the build state icon.
    :return: content of a file.
    """
    if not build:
        response = send_file("static/status_images/unknown.png", mimetype='image/png')
        if no_cache:
            response.headers['Cache-Control'] = 'public, max-age=60'
        return response

    if build.state in ["importing", "pending", "starting", "running"]:
        # The icon is about to change very soon, disable caches:
        # https://help.github.com/articles/about-anonymized-image-urls/
        response = send_file("static/status_images/in_progress.png",
                             mimetype='image/png')
        response.headers['Cache-Control'] = 'no-cache'
        return response

    if build.state in ["succeeded", "skipped"]:
        response = send_file("static/status_images/succeeded.png", mimetype='image/png')
    elif build.state == "failed":
        response = send_file("static/status_images/failed.png", mimetype='image/png')
    else:
        response = send_file("static/status_images/unknown.png", mimetype='image/png')

    if no_cache:
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Pragma'] = 'no-cache'
    return response


def req_with_pagination(f):
    """
    Parse 'page=' option from GET url, and place it as the argument
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            page = flask.request.args.get('page', 1)
            page = int(page)
        except ValueError as err:
            raise ObjectNotFound("Invalid pagination format") from err
        return f(*args, page=page, **kwargs)
    return wrapper
