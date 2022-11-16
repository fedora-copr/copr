"""
Authentication-related code for communication with FAS, Kerberos, LDAP, etc.
"""

import time
from urllib.parse import urlparse
import flask
import ldap
from openid_teams.teams import TeamsRequest
from coprs import oid
from coprs import app
from coprs.exceptions import CoprHttpException, AccessRestricted
from coprs.logic.users_logic import UsersLogic


class UserAuth:
    """
    Facade for choosing the correct authentication mechanism (FAS, Kerberos),
    and interacting with it. All decision making based on
    `app.config["FAS_LOGIN"]` and `app.config["KRB5_LOGIN"]` should be
    encapsulated within this class.
    """

    @staticmethod
    def logout():
        """
        Log out the current user
        """
        if flask.g.user:
            app.logger.info("User '%s' logging out", flask.g.user.name)

        FedoraAccounts.logout()
        Kerberos.logout()

        flask.flash("You were signed out")
        return flask.redirect(oid.get_next_url())

    @staticmethod
    def current_username():
        """
        Is a user logged-in? Return their username
        """
        return FedoraAccounts.username() or Kerberos.username()

    @staticmethod
    def user_object(oid_resp=None, username=None):
        """
        Get or Create a `models.User` object based on the input parameters
        """
        if oid_resp:
            # All metadata for the user craation are in oid_resp.
            return FedoraAccounts.user_from_response(oid_resp)

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
    def get_or_create_user(username):
        """
        Get the user from DB, or create a new one without any additional
        metadata if it doesn't exist.
        """
        user = UsersLogic.get(username).first()
        if user:
            return user
        app.logger.info("Login for user '%s', "
                        "creating a database record", username)
        return UsersLogic.create_user_wrapper(username)


class GroupAuth:
    """
    Facade for choosing the correct user group authority (FAS, LDAP),
    and interacting with it. All decision making based on
    `app.config["FAS_LOGIN"]` and `app.config["KRB5_LOGIN"]` should be
    encapsulated within this class.
    """

    @classmethod
    def update_user_groups(cls, user, oid_resp=None):
        """
        Upon a successful login, try to (a) load the list of groups from
        authoritative source, and (b) (re)set the user.openid_groups.
        """

        def _do_update(user, grouplist):
            user.openid_groups = {
                "fas_groups": grouplist,
            }

        if oid_resp:
            _do_update(user, OpenIDGroups.group_names(oid_resp))
            return

        # If we have a LDAP pre-configured, now is the right time to load the
        # data, or fail.
        keys = ["LDAP_URL", "LDAP_SEARCH_STRING"]
        if all(app.config[k] for k in keys):
            _do_update(user, LDAPGroups.group_names(user.username))
            return

        # We only ever call update_user_groups() with oid_resp!= None with FAS
        assert not app.config["FAS_LOGIN"]

        app.logger.warning("Nowhere to get groups from")
        # This copr doesn't support groups.
        _do_update(user, [])


class FedoraAccounts:
    """
    Authentication via user accounts from
    https://accounts.fedoraproject.org
    """

    @classmethod
    def username(cls):
        """
        Is a user logged-in? Return their username
        """
        if "openid" in flask.session:
            return cls.fed_raw_name(flask.session["openid"])
        return None

    @staticmethod
    def login():
        """
        If not already logged-in, perform a log-in request
        """
        if flask.g.user is not None:
            return flask.redirect(oid.get_next_url())

        # If the login is successful, we are redirected to function decorated
        # with the `@oid.after_login`
        team_req = TeamsRequest(["_FAS_ALL_GROUPS_"])
        return oid.try_login(app.config["OPENID_PROVIDER_URL"],
                            ask_for=["email", "timezone"],
                            extensions=[team_req])

    @staticmethod
    def logout():
        """
        Log out the current user
        """
        flask.session.pop("openid", None)

    @staticmethod
    def is_user_allowed(username):
        """
        Is this user allowed to log in?
        """
        if not username:
            return False
        if not app.config["USE_ALLOWED_USERS"]:
            return True
        return username in app.config["ALLOWED_USERS"]

    @staticmethod
    def fed_raw_name(oidname):
        """
        Convert the full `oidname` to username
        """
        oidname_parse = urlparse(oidname)
        if not oidname_parse.netloc:
            return oidname
        config_parse = urlparse(app.config["OPENID_PROVIDER_URL"])
        return oidname_parse.netloc.replace(".{0}".format(config_parse.netloc), "")

    @classmethod
    def user_from_response(cls, oid_resp):
        """
        Create a `models.User` object from FAS response
        """
        username = cls.fed_raw_name(oid_resp.identity_url)
        user = UserAuth.get_or_create_user(username)
        # Update user attributes from FAS
        user.mail = oid_resp.email
        user.timezone = oid_resp.timezone
        GroupAuth.update_user_groups(user, oid_resp)
        return user


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
        return cls._krb5_login_redirect(next_url=oid.get_next_url())

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
        GroupAuth.update_user_groups(user)
        return user

    @staticmethod
    def _krb5_login_redirect(next_url=None):
        if app.config['KRB5_LOGIN']:
            # Pick the first one for now.
            return flask.redirect(flask.url_for("apiv3_ns.gssapi_login",
                                                next=next_url))
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
        return self.send_request(self.search_string, attrs, ffilter)[0]

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
            return None
        return user[1]["memberOf"]

    def _build_filter(self, filters):
        # pylint: disable=no-self-use
        filters = filters or {"objectclass": "*"}
        ffilter = ["({0}={1})".format(k, v) for k, v in filters.items()]
        return "(&{0})".format("".join(ffilter))
