from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, POST
from ..exceptions import CoprValidationException


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

    def create_from_url(self, ownername, projectname, url):
        if len(url.split()) > 1:
            raise CoprValidationException("This method doesn't allow submitting multiple URLs at once. "
                                          "Use `create_from_urls` instead.")
        return self.create_from_urls(ownername, projectname, [url])[0]

    def create_from_file(self, ownername, projectname, path):
        endpoint = "/build/create/upload"
        f = open(path, "rb")
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "pkgs": (os.path.basename(f.name), f, "application/x-rpm"),
        }
        request = FileRequest(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
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
        return response.munchify()

    def create_from_pypi(self, ownername, projectname, pypi_package_name,
                         pypi_package_version=None, python_versions=None):
        endpoint = "/build/create/pypi"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "python_versions": python_versions or [3, 2],
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()

    def create_from_rubygems(self, ownername, projectname, gem_name):
        endpoint = "/build/create/rubygems"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "gem_name": gem_name,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return response.munchify()
