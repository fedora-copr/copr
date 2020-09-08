import os
from ..helpers import config_from_file
from ..requests import Request, munchify
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class BaseProxy(object):
    """
    Parent class for all other proxies
    """

    def __init__(self, config):
        self.config = config

    @classmethod
    def create_from_config_file(cls, path=None):
        config = config_from_file(path)
        return cls(config)

    @property
    def api_base_url(self):
        return os.path.join(self.config["copr_url"], "api_3", "")

    @property
    def auth(self):
        return self.config["login"], self.config["token"]

    def home(self):
        """
        Call the Copr APIv3 base URL

        :return: Munch
        """
        endpoint = ""
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return munchify(response)

    def auth_check(self):
        """
        Call an endpoint protected by login to check whether the user auth key is valid

        :return: Munch
        """
        endpoint = "/auth-check"
        request = Request(endpoint, api_base_url=self.api_base_url, auth=self.auth)
        response = request.send()
        return munchify(response)
