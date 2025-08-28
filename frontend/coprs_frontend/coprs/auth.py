"""
Authentication-related code for communication with FAS, Kerberos, LDAP, etc.
"""

import time
import flask
import ldap
from coprs import app
from coprs.exceptions import CoprHttpException, AccessRestricted
from coprs.logic.users_logic import UsersLogic
from coprs.oidc import oidc_username_from_userinfo


class UserAuth:
    """
    Facade for choosing the correct authentication mechanism (FAS, Kerberos),
    and interacting with it. All decision making based on
    `app.config["FAS_LOGIN"]` and `app.config["KRB5_LOGIN"]` should be
    encapsulated within this class.
    """

    @classmethod
    def next_url(cls):
        """
        Where should user be redirected after a successful login?

        We used to get the next URL through `oid.get_next_url()` but there is
        no such equivalent for our current OIDC client. We need to set and get
        it manually. It's a good idea to stay consistent with its logic.
        https://github.com/pallets-eco/flask-openid/blob/1eccf8a/flask_openid.py#L413
        """
        if url := flask.request.values.get("next"):
            if cls._is_safe_next_url(url):
                return url

        # When reading the URL from a session, pop it so it's usable only once
        if url := flask.session.pop("next", None):
            if cls._is_safe_next_url(url):
                return url

        if url := flask.request.referrer:
            if cls._is_safe_next_url(url):
                return url

        if cls.current_username():
            return flask.url_for(
                "coprs_ns.coprs_by_user", username=cls.current_username())
        return "/"

    @staticmethod
    def _is_safe_next_url(url):
        return url.startswith(flask.request.url_root) or url.startswith("/")

    @classmethod
    def logout(cls):
        """
        Log out the current user
        """
        if flask.g.user:
            app.logger.info("User '%s' logging out", flask.g.user.name)

        Kerberos.logout()
        OpenIDConnect.logout()

        flask.flash("You were signed out")
        return flask.redirect(cls.next_url())

    @staticmethod
    def current_username():
        """
        Is a user logged-in? Return their username
        """
        return Kerberos.username() or OpenIDConnect.username()

    @staticmethod
    def user_object(username=None):
        """
        Get or Create a `models.User` object based on the input parameters
        """
        if app.config["FAS_LOGIN"] and app.config["KRB5_LOGIN"]:
            user = Kerberos.user_from_username(username)
            if not user.mail:
                # We can not continue (with perhaps freshly created user object)
                # now because we don't have the necessary user metadata (e-mail
                # and groups).  TODO: obtain the info somehow on demand here!
                raise AccessRestricted(
                    "Valid GSSAPI authentication supplied for user '{}', but this "
                    "user doesn't exist in the Copr build system.  Please log-in "
                    "using the web-UI (without GSSAPI) first.".format(username)
                )
            return user

        if app.config["KRB5_LOGIN"]:
            return Kerberos.user_from_username(username, True)

        raise CoprHttpException("No auth method available")

    @staticmethod
    def get_or_create_user(username, email=None, timezone=None):
        """
        Get the user from DB, or create a new one without any additional
        metadata if it doesn't exist.
        """
        user = UsersLogic.get(username).first()
        if user:
            if email is not None:
                user.mail = email
            return user
        app.logger.info("Login for user '%s', "
                        "creating a database record", username)
        return UsersLogic.create_user_wrapper(username, email, timezone)


class GroupAuth:
    """
    Facade for choosing the correct user group authority (FAS, LDAP),
    and interacting with it. All decision making based on
    `app.config["FAS_LOGIN"]` and `app.config["KRB5_LOGIN"]` should be
    encapsulated within this class.
    """
    @classmethod
    def update_user_groups(cls, user, groups=None):
        """
        Upon a successful login, try to (a) load the list of groups from
        authoritative source, and (b) (re)set the user.openid_groups.
        """
        def _do_update(user, grouplist):
            user.openid_groups = {
                "fas_groups": grouplist,
            }
        if not groups:
            groups = []

        if not isinstance(groups, list):
            app.logger.error("groups should be a list object")
            return

        app.logger.info(f"groups add: {groups}")
        _do_update(user, groups)
        return


class Kerberos:
    """
    Authentication via Kerberos / GSSAPI
    """

    @staticmethod
    def username():
        """
        Is a user logged-in? Return their username
        """
        if "krb5_login" in flask.session:
            return flask.session["krb5_login"]
        return None

    @classmethod
    def login(cls):
        """
        If not already logged-in, perform a log-in request
        """
        return cls._krb5_login_redirect(next_url=UserAuth.next_url())

    @staticmethod
    def logout():
        """
        Log out the current user
        """
        flask.session.pop("krb5_login", None)

    @staticmethod
    def user_from_username(username, load_metadata=False):
        """
        Create a `models.User` object from Kerberos username
        When 'load_metadata' is True, we have to obtain and set the necessary
        user metadata (groups, email).
        """
        user = UserAuth.get_or_create_user(username)
        if not load_metadata:
            return user

        # Create a new user object
        krb_config = app.config['KRB5_LOGIN']
        user.mail = username + "@" + krb_config['email_domain']
        keys = ["LDAP_URL", "LDAP_SEARCH_STRING"]
        if all(app.config[k] for k in keys):
            GroupAuth.update_user_groups(user, LDAPGroups.group_names(user.username))
        return user

    @staticmethod
    def _krb5_login_redirect(next_url=None):
        if app.config['KRB5_LOGIN']:
            # Pick the first one for now.
            return flask.redirect(
                # url_for takes the namespace + class method converted from camelCase to snake_case
                flask.url_for("apiv3_ns.general_gssapi_login", next=next_url)
            )
        flask.flash("Unable to pick krb5 login page", "error")
        return flask.redirect(flask.url_for("coprs_ns.coprs_show"))


class OpenIDGroups:
    """
    User groups from FAS (and OpenID in general)
    """

    @staticmethod
    def group_names(resp):
        """
        Return a list of group names (that a user belongs to) from FAS response
        """
        if "lp" in resp.extensions:
            # name space for the teams extension
            team_resp = resp.extensions['lp']
            return team_resp.teams
        return None


class LDAPGroups:
    """
    User groups from LDAP
    """

    @staticmethod
    def group_names(username):
        """
        Return a list of group names that a user belongs to
        """
        ldap_client = LDAP(app.config["LDAP_URL"],
                           app.config["LDAP_SEARCH_STRING"])
        groups = []
        for group in ldap_client.get_user_groups(username):
            group = group.decode("utf-8")
            attrs = dict([tuple(x.split("=")) for x in group.split(",")])
            groups.append(attrs["cn"])
        return groups


class LDAP:
    """
    High-level facade for interacting with LDAP server
    """

    def __init__(self, url, search_string):
        self.url = url
        self.search_string = search_string

    def send_request(self, ou, attrs, ffilter):
        """
        Send a /safe/ request to a LDAP server
        """
        return self._send_request_repeatedly(ou, attrs, ffilter)

    def _send_request_repeatedly(self, ou, attrs, ffilter):
        i = 0
        while True:
            i += 1
            try:
                return self._send_request(ou, attrs, ffilter)
            except ldap.SERVER_DOWN as ex:
                print(str(ex))
                time.sleep(0.5)

    def _send_request(self, ou, attrs, ffilter):
        """
        Send a single request to a LDAP server
        """
        try:
            connect = ldap.initialize(self.url)
            return connect.search_s(ou, ldap.SCOPE_ONELEVEL,
                                    ffilter, attrs)
        except ldap.SERVER_DOWN as ex:
            msg = ex.args[0]["desc"]
            raise CoprHttpException(msg) from ex

    def query_one(self, attrs, filters=None):
        """
        Query one object from LDAP
        """
        ffilter = self._build_filter(filters)
        objects = self.send_request(self.search_string, attrs, ffilter)
        if len(objects) != 1:
            app.logger.error("Bad number of LDAP objects %s for filters %s",
                             len(objects), filters)
            return None
        return objects[0]

    def get_user(self, username):
        """
        Return an LDAP user
        """
        attrs = [
            "cn",
            "uid",
            "memberOf",
            "mail",
        ]
        filters = {
            "objectclass": "*",
            "uid": username,
        }
        return self.query_one(attrs, filters)

    def get_user_groups(self, username):
        """
        Return a list of groups that a user belongs to
        """
        user = self.get_user(username)
        if not user:
            return []
        return user[1].get("memberOf", [])

    def _build_filter(self, filters):
        # pylint: disable=no-self-use
        filters = filters or {"objectclass": "*"}
        ffilter = ["({0}={1})".format(k, v) for k, v in filters.items()]
        return "(&{0})".format("".join(ffilter))


class OpenIDConnect:
    """
    Authentication via OpenID Connect
    """
    @staticmethod
    def username():
        """
        Is a user logged-in? Return their username
        """
        if "oidc" in flask.session:
            return flask.session["oidc"]
        return None

    @staticmethod
    def logout():
        """
        Log out the current user
        """
        flask.session.pop("oidc", None)

    @staticmethod
    def user_from_userinfo(userinfo):
        """
        Create a `models.User` object from oidc user info
        """
        if not userinfo:
            return None

        zoneinfo = userinfo['zoneinfo'] if 'zoneinfo' in userinfo \
            and userinfo['zoneinfo'] else None
        username = oidc_username_from_userinfo(app.config, userinfo)

        user = UserAuth.get_or_create_user(username, userinfo['email'], zoneinfo)
        GroupAuth.update_user_groups(user, OpenIDConnect.groups_from_userinfo(userinfo))
        return user

    @staticmethod
    def groups_from_userinfo(userinfo):
        """
        Create a `models.User` object from oidc user info
        """
        if not userinfo:
            return None

        return userinfo.get("groups")
