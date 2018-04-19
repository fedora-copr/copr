from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, POST


class ProjectChrootProxy(BaseProxy):

    def get(self, ownername, projectname, chrootname):
        endpoint = "/project-chroot"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def get_build_config(self, ownername, projectname, chrootname):
        endpoint = "/project-chroot/build-config"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def edit(self, ownername, projectname, chrootname, packages=None, repos=None, comps=None, delete_comps=False):
        endpoint = "/project-chroot/edit"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        data = {
            "repos": " ".join(repos or []),
            "buildroot_pkgs": " ".join(packages or []),
            "delete_comps": delete_comps,
        }
        files = {}
        if comps:
            comps_f = open(comps, "rb")
            files["upload_comps"] = (os.path.basename(comps_f.name), comps_f, "application/text")

        request = FileRequest(endpoint, api_base_url=self.api_base_url, method=POST,
                              params=params, data=data, files=files, auth=self.auth)
        response = request.send()
        return response.munchify()
