from __future__ import absolute_import

from . import BaseProxy
from ..requests import Request


class GeneralProxy(BaseProxy):

    def home(self):
        """
        Call the Copr APIv3 base URL
        :return: Munch
        """
        endpoint = ""
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return response.munchify()

    def auth_check(self):
        """
        Call an endpoint protected by login to check whether the user auth key is valid
        :return: Munch
        """
        endpoint = "/auth-check"
        request = Request(endpoint, api_base_url=self.api_base_url, auth=self.auth)
        response = request.send()
        return response.munchify()
