import errno
import json
import time
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from future.utils import raise_from

import requests_gssapi

from ..requests import Request, munchify, requests
from ..helpers import for_all_methods, bind_proxy, config_from_file
from ..exceptions import CoprAuthException, CoprConfigException


@for_all_methods(bind_proxy)
class BaseProxy(object):
    """
    Parent class for all other proxies
    """

    def __init__(self, config):
        self.config = config
        self._auth_token_cached = None
        self._auth_username = None
        self.request = Request(api_base_url=self.api_base_url, connection_attempts=config.get("connection_attempts", 1))

    @classmethod
    def create_from_config_file(cls, path=None):
        config = config_from_file(path)
        return cls(config)

    @property
    def api_base_url(self):
        return os.path.join(self.config["copr_url"], "api_3", "")

    @property
    def auth(self):
        if self._auth_token_cached:
            return self._auth_token_cached
        if self.config.get("token"):
            self._auth_token_cached = self.config["login"], self.config["token"]
            self._auth_username = self.config.get("username")
        elif self.config.get("gssapi"):
            session_data = self._get_session_cookie_via_gssapi()
            self._auth_token_cached = session_data["session"]
            self._auth_username = session_data["name"]
        else:
            msg = "GSSAPI disabled and login:token is invalid ({0}:{1})".format(
                self.config.get("login", "NOT_SET"),
                self.config.get("token", "NOT_SET"),
            )
            raise CoprAuthException(msg)
        return self._auth_token_cached

    def _get_session_cookie_via_gssapi(self):
        """
        Return the cached session for the configured username.  If not already
        cached, new self.get_session_via_gssapi() is performed and result is
        cached into ~/.config/copr/<session_file>.
        """
        session_data = None
        url = urlparse(self.config["copr_url"]).netloc
        cachedir = os.path.join(os.path.expanduser("~"), ".cache", "copr")

        try:
            os.makedirs(cachedir)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        session_file = os.path.join(cachedir, url+"-session")

        if os.path.exists(session_file):
            with open(session_file, "r") as file:
                session_data = json.load(file)

        if session_data and session_data["expiration"] > time.time():
            return session_data

        # TODO: create Munch sub-class that returns serializable dict, we
        # have something like that in Cli: cli/copr_cli/util.py:serializable()
        session_data = self.get_session_via_gssapi()
        session_data = session_data.__dict__
        session_data.pop("__response__", None)
        session_data.pop("__proxy__", None)

        with open(session_file, "w") as file:
            session_data["expiration"] = time.time() + 10*3600  # +10 hours
            file.write(json.dumps(session_data, indent=4) + "\n")

        return session_data

    def get_session_via_gssapi(self):
        """
        Obtain a _new_ session using GSSAPI route

        :return: Munch, provides user's "id", "name", "session" cookie, and
            "expiration".
        """
        url = self.config["copr_url"] + "/api_3/gssapi_login/"
        session = requests.Session()
        auth = requests_gssapi.HTTPSPNEGOAuth(opportunistic_auth=True)
        try:
            response = session.get(url, auth=auth)
        except  requests_gssapi.exceptions.SPNEGOExchangeError as err:
            msg = "Can not get session for {0} cookie via GSSAPI: {1}".format(
                self.config["copr_url"], err)
            raise_from(CoprAuthException(msg), err)

        if response.status_code != 200:
            raise CoprAuthException("GSSAPI route {0} returned status {1}".format(
                url, response.status_code,
            ))

        retval = munchify(response)
        retval.session = response.cookies.get("session")
        return retval

    def home(self):
        """
        Call the Copr APIv3 base URL

        :return: Munch
        """
        endpoint = ""
        response = self.request.send(endpoint=endpoint)
        return munchify(response)

    def auth_check(self):
        """
        Call an endpoint protected by login to check whether the user auth key is valid

        :return: Munch
        """
        endpoint = "/auth-check"
        self.request.auth = self.auth
        response = self.request.send(endpoint=endpoint)
        return munchify(response)


    def auth_username(self):
        """
        Return the username (string) assigned to this configuration.  May
        contact the server and authenticate if needed.
        """
        if not self._auth_username:
            # perform authentication as a side effect
            _ = self.auth
        return self._auth_username
