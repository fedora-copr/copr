from __future__ import absolute_import
from . import BaseProxy
from ..requests import Request, POST


class BuildProxy(BaseProxy):
    def get(self, build_id):
        endpoint = "/build/{}".format(build_id)
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return response.munchify()

    def cancel(self, build_id):
        endpoint = "/build/cancel/{}".format(build_id)
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()
