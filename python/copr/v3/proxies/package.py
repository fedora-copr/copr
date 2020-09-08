from __future__ import absolute_import
from . import BaseProxy
from .build import BuildProxy
from ..requests import Request, munchify, POST
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class PackageProxy(BaseProxy):

    def get(self, ownername, projectname, packagename,
            with_latest_build=False, with_latest_succeeded_build=False):
        """
        Return a package

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :param bool with_latest_build: The result will contain "builds" dictionary with the latest
                                       submitted build of this particular package within the project
        :param bool with_latest_succeeded_build: The result will contain "builds" dictionary with
                                                 the latest successful build of this particular
                                                 package within the project.
        :return: Munch
        """
        endpoint = "/package"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "packagename": packagename,
            "with_latest_build": with_latest_build,
            "with_latest_succeeded_build": with_latest_succeeded_build,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def get_list(self, ownername, projectname, pagination=None,
                 with_latest_build=False, with_latest_succeeded_build=False):
        """
        Return a list of packages

        :param str ownername:
        :param str projectname:
        :param pagination:
        :param bool with_latest_build: The result will contain "builds" dictionary with the latest
                                       submitted build of this particular package within the project
        :param bool with_latest_succeeded_build: The result will contain "builds" dictionary with
                                                 the latest successful build of this particular
                                                 package within the project.
        :return: Munch
        """
        endpoint = "/package/list"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "with_latest_build": with_latest_build,
            "with_latest_succeeded_build": with_latest_succeeded_build,
        }
        params.update(pagination or {})

        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def add(self, ownername, projectname, packagename, source_type, source_dict):
        """
        Add a package to a project

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :param str source_type: http://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        :param dict source_dict: http://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        :return: Munch
        """
        endpoint = "/package/add/{ownername}/{projectname}/{package_name}/{source_type_text}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
            "source_type_text": source_type,
        }
        data = {
            "package_name": packagename,
        }
        data.update(source_dict)
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def edit(self, ownername, projectname, packagename, source_type=None, source_dict=None):
        """
        Edit a package in a project

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :param source_type: http://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        :param dict source_dict: http://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        :return: Munch
        """
        endpoint = "/package/edit/{ownername}/{projectname}/{package_name}/{source_type_text}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
            "source_type_text": source_type,
        }
        data = {
            "package_name": packagename,
        }
        data.update(source_dict or {})
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def reset(self, ownername, projectname, packagename):
        """
        Reset a package configuration, meaning that previously selected `source_type`
        for the package and also all the source configuration previously defined by
        `source_dict` will be nulled.

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :return: Munch
        """
        endpoint = "/package/reset"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return munchify(response)

    def build(self, ownername, projectname, packagename, buildopts=None, project_dirname=None):
        """
        Create a build from a package configuration

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/package/build"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
            "project_dirname": project_dirname,
        }
        build_proxy = BuildProxy(self.config)
        return build_proxy._create(endpoint, data, buildopts=buildopts)

    def delete(self, ownername, projectname, packagename):
        """
        Delete a package from a project

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :return: Munch
        """
        endpoint = "/package/delete"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "package_name": packagename,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, data=data, method=POST, auth=self.auth)
        response = request.send()
        return munchify(response)
