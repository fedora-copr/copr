from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, POST


class ModuleProxy(BaseProxy):

    def build_from_url(self, ownername, projectname, scmurl, branch="master"):
        endpoint = "/module/build"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "scmurl": scmurl,
            "branch": branch,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return response.munchify()

    def build_from_file(self, ownername, projectname, path):
        endpoint = "/module/build"
        f = open(path, "rb")
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "modulemd": (os.path.basename(f.name), f, "application/x-rpm")
        }
        request = FileRequest(endpoint, api_base_url=self.api_base_url, method=POST,
                              params=params, data=data, auth=self.auth)
        response = request.send()
        return response.munchify()
