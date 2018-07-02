from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, munchify, POST


class ModuleProxy(BaseProxy):

    def build_from_url(self, ownername, projectname, url, branch="master"):
        """
        Build a module from a URL pointing to a modulemd YAML file

        :param str ownername:
        :param str projectname:
        :param str url: URL pointing to a raw .yaml file
        :param str branch:
        :return: Munch
        """
        endpoint = "/module/build/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "scmurl": url,
            "branch": branch,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def build_from_file(self, ownername, projectname, path):
        """
        Build a module from a local modulemd YAML file

        :param str ownername:
        :param str projectname:
        :param str path:
        :return: Munch
        """
        endpoint = "/module/build/{ownername}/{projectname}"
        f = open(path, "rb")
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        files = {
            "modulemd": (os.path.basename(f.name), f, "application/x-rpm")
        }
        request = FileRequest(endpoint, api_base_url=self.api_base_url, method=POST,
                              params=params, files=files, auth=self.auth)
        response = request.send()
        return munchify(response)
