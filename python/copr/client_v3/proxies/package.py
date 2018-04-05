from __future__ import absolute_import
from . import BaseProxy
from ..requests import Request, POST


class PackageProxy(BaseProxy):
    def get_list(self, ownername, projectname, pagination=None):
        endpoint = "/package/list"
        data = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data.update(pagination.to_dict() if pagination else {})

        request = Request(endpoint, api_base_url=self.api_base_url, params=data)
        response = request.send()
        return response.munchify()

    def edit(self, ownername, projectname, packagename, source_type_text, source_dict):
        endpoint = "/package/edit"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
            "source_type_text": source_type_text,
        }
        data.update(source_dict)
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()
