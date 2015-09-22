import base64
import datetime
import functools
from functools import wraps

from netaddr import IPAddress, IPNetwork
import re
import flask

from openid_teams.teams import TeamsRequest

from coprs import app
from coprs import db
from coprs import helpers
from coprs import models
from coprs import oid
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic


def fed_openidize_name(name):
    """
    Create proper Fedora OpenID name from short name.

    >>> fedoraoid == fed_openidize_name(user.name)
    True
    """

    return "http://{0}.id.fedoraproject.org/".format(name)


def create_user_wrapper(username, email, timezone=None):
    expiration_date_token = datetime.date.today() + \
        datetime.timedelta(
            days=flask.current_app.config["API_TOKEN_EXPIRATION"])

    copr64 = base64.b64encode(b"copr") + b"##"
    user = models.User(username=username, mail=email,
                       timezone=timezone,
                       api_login=copr64.decode("utf-8") + helpers.generate_api_token(
                           app.config["API_TOKEN_LENGTH"] - len(copr64)),
                       api_token=helpers.generate_api_token(
                           app.config["API_TOKEN_LENGTH"]),
                       api_token_expiration=expiration_date_token)
    return user


def fed_raw_name(oidname):
    return oidname.replace(".id.fedoraproject.org/", "") \
                  .replace("http://", "")


def krb_strip_realm(fullname):
    return re.sub(r'@.*', '', fullname)


@app.before_request
def set_empty_user():
    flask.g.user = None


@app.before_request
def lookup_current_user():
    flask.g.user = username = None
    if "openid" in flask.session:
        username = fed_raw_name(flask.session["openid"])
    elif "krb5_login" in flask.session:
        username = flask.session["krb5_login"]

    if username:
        flask.g.user = models.User.query.filter(
            models.User.username == username).first()


@app.errorhandler(404)
def page_not_found(message):
    return flask.render_template("404.html", message=message), 404


@app.errorhandler(403)
def access_restricted(message):
    return flask.render_template("403.html", message=message), 403


misc = flask.Blueprint("misc", __name__)


@misc.route(app.config['KRB5_LOGIN_BASEURI'] + "<name>/", methods=["GET"])
def krb5_login(name):
    """
    Handle the Kerberos authentication.

    Note that if we are able to get here, either the user is authenticated
    correctly, or apache is mis-configured and it does not perform KRB
    authentication at all.  Note also, even if that can be considered ugly, we
    are reusing oid's get_next_url feature with kerberos login.
    """

    # Already logged in?
    if flask.g.user is not None:
        return flask.redirect(oid.get_next_url())

    krb_config = app.config['KRB5_LOGIN']

    found = None
    for key in krb_config.keys():
        if krb_config[key]['URI'] == name:
            found = key
            break

    if not found:
        # no KRB5_LOGIN.<name> configured in copr.conf
        return flask.render_template("404.html"), 404

    if 'REMOTE_USER' not in flask.request.environ:
        nocred = "Kerberos authentication failed (no credentials provided)"
        return flask.render_template("403.html", message=nocred), 403

    krb_username = flask.request.environ['REMOTE_USER']
    username = krb_strip_realm(krb_username)

    krb_login = (
        models.Krb5Login.query
        .filter(models.Krb5Login.config_name == key)
        .filter(models.Krb5Login.primary == username)
        .first()
    )
    if krb_login:
        flask.g.user = krb_login.user
        flask.session['krb5_login'] = krb_login.user.name
        flask.flash(u"Welcome, {0}".format(flask.g.user.name))
        return flask.redirect(oid.get_next_url())

    # We need to create row in 'krb5_login' table
    user = models.User.query.filter(models.User.username == username).first()
    if not user:
        # Even the item in 'user' table does not exist, create _now_
        email = username + "@" + krb_config[key]['email_domain']
        user = create_user_wrapper(username, email)
        db.session.add(user)

    krb_login = models.Krb5Login(user=user, primary=username, config_name=key)
    db.session.add(krb_login)
    db.session.commit()

    flask.flash(u"Welcome, {0}".format(user.name))
    flask.g.user = user
    flask.session['krb5_login'] = user.name
    return flask.redirect(oid.get_next_url())


@misc.route("/login/", methods=["GET"])
@oid.loginhandler
def login():
    if flask.g.user is not None:
        return flask.redirect(oid.get_next_url())
    else:
        # a bit of magic
        team_req = TeamsRequest(["_FAS_ALL_GROUPS_"])
        return oid.try_login("https://id.fedoraproject.org/",
                             ask_for=["email", "timezone"],
                             extensions=[team_req])


@oid.after_login
def create_or_login(resp):
    flask.session["openid"] = resp.identity_url
    fasusername = resp.identity_url.replace(
        ".id.fedoraproject.org/", "").replace("http://", "")

    # kidding me.. or not
    if fasusername and (
            (
                app.config["USE_ALLOWED_USERS"] and
                fasusername in app.config["ALLOWED_USERS"]
            ) or not app.config["USE_ALLOWED_USERS"]):

        username = fed_raw_name(resp.identity_url)
        user = models.User.query.filter(
            models.User.username == username).first()
        if not user:  # create if not created already
            user = create_user_wrapper(username, resp.email, resp.timezone)
        else:
            user.mail = resp.email
            user.timezone = resp.timezone
        if "lp" in resp.extensions:
            team_resp = resp.extensions['lp']  # name space for the teams extension
            user.openid_groups = {"fas_groups": team_resp.teams}

        db.session.add(user)
        db.session.commit()
        flask.flash(u"Welcome, {0}".format(user.name))
        flask.g.user = user

        if flask.request.url_root == oid.get_next_url():
            return flask.redirect(flask.url_for("coprs_ns.coprs_by_owner",
                                                username=user.name))
        return flask.redirect(oid.get_next_url())
    else:
        flask.flash("User '{0}' is not allowed".format(fasusername))
        return flask.redirect(oid.get_next_url())


@misc.route("/logout/")
def logout():
    flask.session.pop("openid", None)
    flask.session.pop("krb5_login", None)
    flask.flash(u"You were signed out")
    return flask.redirect(oid.get_next_url())


def api_login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        apt_login = None
        if "Authorization" in flask.request.headers:
            base64string = flask.request.headers["Authorization"]
            base64string = base64string.split()[1].strip()
            userstring = base64.b64decode(base64string)
            (apt_login, token) = userstring.decode("utf-8").split(":")
        token_auth = False
        if token and apt_login:
            user = UsersLogic.get_by_api_login(apt_login).first()
            if (user and user.api_token == token and
                    user.api_token_expiration >= datetime.date.today()):

                token_auth = True
                flask.g.user = user
        if not token_auth:
            output = {
                "output": "notok",
                "error": "Login invalid/expired. "
                         "Please visit https://copr.fedoraproject.org/api "
                         "get or renew your API token.",
            }
            jsonout = flask.jsonify(output)
            jsonout.status_code = 500
            return jsonout
        return f(*args, **kwargs)
    return decorated_function


def login_required(role=helpers.RoleEnum("user")):
    def view_wrapper(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if flask.g.user is None:
                return flask.redirect(flask.url_for("misc.login",
                                                    next=flask.request.url))

            if role == helpers.RoleEnum("admin") and not flask.g.user.admin:
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


def intranet_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        ip_addr = IPAddress(flask.request.remote_addr)
        accept_ranges = set(app.config.get("INTRANET_IPS", []))
        accept_ranges.add("127.0.0.1")  # always accept from localhost
        if not any(ip_addr in IPNetwork(addr_or_net) for addr_or_net in accept_ranges):
            return ("Stats can be update only from intranet hosts, "
                    "not {}, check config\n".format(flask.request.remote_addr)), 403

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
