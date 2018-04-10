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

    def create_from_urls(self, ownername, projectname, urls):
        endpoint = "/build/create/url"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "pkgs": " ".join(urls),
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()

    def create_from_scm(self, ownername, projectname, clone_url, committish="", subdirectory="", spec="",
                        scm_type="git", srpm_build_method="rpkg"):
        endpoint = "/build/create/scm"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "clone_url": clone_url,
            "committish": committish,
            "subdirectory": subdirectory,
            "spec": spec,
            "scm_type": scm_type,
            "srpm_build_method": srpm_build_method,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()[0]
