from __future__ import absolute_import
from . import BaseProxy
from ..requests import Request, POST


class PackageProxy(BaseProxy):

    def get(self, ownername, projectname, packagename):
        endpoint = "/package"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "packagename": packagename,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def get_list(self, ownername, projectname, pagination=None):
        endpoint = "/package/list"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        params.update(pagination.to_dict() if pagination else {})

        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def add(self, ownername, projectname, packagename, source_type_text, source_dict):
        endpoint = "/package/add"
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

    def reset(self, ownername, projectname, packagename):
        endpoint = "/package/reset"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()

    def build(self, ownername, projectname, packagename):
        endpoint = "/package/build"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()
