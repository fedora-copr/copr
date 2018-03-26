from __future__ import absolute_import
from . import BaseProxy
from ..requests import Request


class PackageProxy(BaseProxy):
    def get_list(self, ownername, projectname, pagination=None):
        endpoint = "/package/list"
        data = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data.update(pagination.to_dict() if pagination else {})

        request = Request(endpoint, api_base_url=self.api_base_url, data=data)
        response = request.send()
        return response.munchify()
