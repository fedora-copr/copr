from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import FileRequest, munchify, POST
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class ModuleProxy(BaseProxy):

    def build_from_url(self, ownername, projectname, url, branch="master",
                       distgit=None):
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
        if distgit is not None:
            data["distgit"] = distgit
        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def build_from_file(self, ownername, projectname, path, distgit=None):
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
        data = None
        if distgit is not None:
            data = {"distgit": distgit}
        request = FileRequest(
            files=files,
            api_base_url=self.api_base_url,
            connection_attempts=self.config.get("connection_attempts", 1)
        )
        response = request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)
