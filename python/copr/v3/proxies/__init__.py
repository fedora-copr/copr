import os

from copr.v3.auth import auth_from_config
from copr.v3.requests import munchify, Request
from ..helpers import for_all_methods, bind_proxy, config_from_file


@for_all_methods(bind_proxy)
class BaseProxy(object):
    """
    Parent class for all other proxies
    """

    def __init__(self, config):
        self.config = config
        self.request = Request(
            api_base_url=self.api_base_url,
            connection_attempts=config.get("connection_attempts", 1)
        )
        self._auth = None

    @classmethod
    def create_from_config_file(cls, path=None):
        config = config_from_file(path)
        return cls(config)

    @property
    def api_base_url(self):
        return os.path.join(self.config["copr_url"], "api_3", "")

    @property
    def auth(self):
        if not self._auth:
            self._auth = auth_from_config(self.config)
        return self._auth

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
        response = self.request.send(endpoint=endpoint, auth=self.auth)
        return munchify(response)

    def auth_username(self):
        """
        Return the username (string) assigned to this configuration.  May
        contact the server and authenticate if needed.
        """
        if not self.auth.username:
            self.auth.make()
        return self.auth.username
