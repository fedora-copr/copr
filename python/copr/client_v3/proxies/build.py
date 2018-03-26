from __future__ import absolute_import
from . import BaseProxy
from ..requests import Request


class BuildProxy(BaseProxy):
    def get(self, build_id):
        endpoint = "/build/{}".format(build_id)
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return response.munchify()

    def cancel(self, build_id):
        # @TODO what should this return?
        # @TODO Should this and other actions be POST and have unified return?
        # endpoint = "/build/{}".format(build_id)
        # request = Request(endpoint)
        # response = request.send()
        # return response.munchify()
        pass
