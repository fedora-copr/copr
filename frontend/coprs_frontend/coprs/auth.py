"""
Authentication-related code for communication with FAS, Kerberos, LDAP, etc.
"""

import os
import time
import flask
import gssapi
import ldap
import ldap.sasl
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
            # Various output types, filter those that we care about.
            # cn=somenamegroup,cn=groups,cn=accounts,dc=domain,dc=example,dc=com
            # ipaUniqueID=<UUID>,cn=hbac,dc=domain,dc=example,dc=com
            # cn=somerole,cn=roles,cn=accounts,dc=domain,dc=example,dc=com
            group_dn = ldap.dn.str2dn(group)
            # Converts to:
            # [[('cn', 'another-group-2', 1)],
            # [('cn', 'groups', 1)],
            # [('ou', 'foo', 1)],
            # [('ou', 'bar', 1)],
            # [('dc', 'company', 1)],
            # [('dc', 'com', 1)]]
            app.logger.debug("Considering memberOf: '%s'", group)
            specifier, group_name, _ = group_dn[0][0]
            if specifier != 'cn':
                continue
            specifier, group_category, _ = group_dn[1][0]
            if specifier != 'cn' or group_category != "groups":
                continue
            groups.append(group_name)
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
        Send a /safe/ request to a LDAP server.  Give up (and raise
        CoprHttpException) once LDAP_TIMEOUT seconds elapse;  a user waiting
        for a log-in must not be blocked for minutes just because the LDAP
        server is unreachable.
        """
        app.logger.debug("LDAP query: attrs=%s ffilter=%s", attrs, ffilter)
        deadline = time.monotonic() + app.config["LDAP_TIMEOUT"]

        app.logger.debug("LDAP initialize: %s", self.url)
        connect = ldap.initialize(self.url)
        # We need both options, they cover different phases:
        # OPT_NETWORK_TIMEOUT limits establishing the TCP connection, i.e. the
        # connect() call, while OPT_TIMEOUT limits waiting for a response to an
        # operation that has already been sent (bind, search).  Without the
        # former, an unreachable server (SYN packets dropped, no RST) keeps the
        # request hanging for as long as the kernel retransmits the SYN, which
        # is over two minutes with the default tcp_syn_retries.  Without the
        # latter, a server that accepts the connection but never answers keeps
        # us waiting forever.
        timeout = self._remaining(deadline)
        app.logger.debug("LDAP set_option: OPT_NETWORK_TIMEOUT=%.1fs", timeout)
        connect.set_option(ldap.OPT_NETWORK_TIMEOUT, timeout)
        app.logger.debug("LDAP set_option: OPT_TIMEOUT=%.1fs", timeout)
        connect.set_option(ldap.OPT_TIMEOUT, timeout)

        try:
            self._bind(connect)
            # Binding could have eaten a part of the budget already
            timeout = self._remaining(deadline)
            app.logger.debug("LDAP set_option: OPT_TIMEOUT=%.1fs", timeout)
            connect.set_option(ldap.OPT_TIMEOUT, timeout)
            app.logger.debug("LDAP search_s: ou=%s", ou)
            result = connect.search_s(ou, ldap.SCOPE_ONELEVEL, ffilter, attrs)
            app.logger.debug("LDAP search_s: %s object(s) returned",
                             len(result))
            return result
        except (ldap.SERVER_DOWN, ldap.TIMEOUT) as ex:
            # Both mean "the server did not give us the data", and both have
            # to become CoprHttpException so that the callers can fall back
            # to the group list from a previous log-in
            try:
                msg = ex.args[0]["desc"]
            except (IndexError, KeyError, TypeError):
                # Unlike SERVER_DOWN, ldap.TIMEOUT is typically raised with
                # no arguments at all
                msg = "unknown error"
            app.logger.error("LDAP server %s is not usable: %s", self.url, msg)
            # This is an outage on the LDAP side, not a client error
            raise CoprHttpException(msg, code=503) from ex
        finally:
            app.logger.debug("LDAP unbind_s")
            try:
                connect.unbind_s()
            except ldap.LDAPError:
                # Closing a connection that never got established fails, and
                # we must not shadow the original exception with that
                pass

    @staticmethod
    def _remaining(deadline):
        """
        Seconds left till 'deadline'.  Never return zero or less, that would
        mean "no timeout at all" for the OPT_* options below.
        """
        return max(deadline - time.monotonic(), 0.1)

    @staticmethod
    def _bind(connect):
        """
        Bind to the LDAP server using a Kerberos ticket obtained from a
        keytab (SASL/GSSAPI), if KRB5_KEYTAB is configured. Otherwise the
        connection stays anonymous.
        """
        keytab = app.config.get("KRB5_KEYTAB")
        if not keytab:
            app.logger.debug("LDAP bind: none, KRB5_KEYTAB is not configured")
            return

        principal = app.config.get("KRB5_PRINCIPAL")
        name = None
        if principal:
            name = gssapi.Name(principal, gssapi.NameType.kerberos_principal)

        # Acquire a ticket from the keytab into a process-local memory
        # ccache, and point Kerberos to it so that the SASL/GSSAPI bind
        # below picks it up.
        ccache = f"MEMORY:copr-ldap-{os.getpid()}"
        app.logger.debug("Kerberos credentials: keytab=%s ccache=%s",
                         keytab, ccache)
        gssapi.Credentials(
            name=name, store={"client_keytab": keytab, "ccache": ccache},
            usage="initiate")
        os.environ["KRB5CCNAME"] = ccache

        app.logger.debug("LDAP sasl_interactive_bind_s: GSSAPI")
        connect.sasl_interactive_bind_s("", ldap.sasl.gssapi())
        app.logger.debug("LDAP Authenticated over GSSAPI")

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
