from __future__ import absolute_import

from . import BaseProxy
from ..requests import Request


class GeneralProxy(BaseProxy):

    def home(self):
        endpoint = ""
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return response.munchify()

    def auth_check(self):
        endpoint = "/auth-check"
        request = Request(endpoint, api_base_url=self.api_base_url, auth=self.auth)
        response = request.send()
        return response.munchify()
