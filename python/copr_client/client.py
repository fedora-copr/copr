#-*- coding: UTF-8 -*-

import json
from pprint import pprint
import os
import sys
import ConfigParser
import logging

logging.basicConfig(level=logging.WARN)
log = logging.getLogger(__name__)


import requests
import exceptions

from .responses import BuildStatusResponse, BuildRequestResponse, \
    CreateProjectResponse, BaseResponse, \
    DeleteProjectResponse, CancelBuildResponse, \
    ProjectDetailsResponse, BuildDetailsResponse, GetProjectsListResponse, ModifyProjectResponse, SearchResponse

__version__ = "0.0.1"
__description__ = "Python client for copr service"


class CoprClient(object):
    def __init__(self, config=None):
        """ Main interface to the copr service
            :param config: Configuration dictionary.
            Fields:
            copr_url - copr service location
            login - user login, used for identification
            token - copr api token
            username - used as copr projects root

        """
        self.token = config.get("token")
        self.login = config.get("login")
        self.username = config.get("username")
        self.copr_url = config.get("copr_url", "http://copr.fedoraproject.org/")

    def __str__(self):
        return "<Copr client. username: {0}, api url: {1}>".format(
            self.username, self.api_url
        )

    @property
    def api_url(self):
        return "{0}/api".format(self.copr_url)

    @staticmethod
    def create_from_file_config(filepath=None):
        """
            Retrieve copr client information from the config file.
            :param filepath: specifies config location, default: "~/.config/copr"
        """
        raw_config = ConfigParser.ConfigParser()
        if not filepath:
            filepath = os.path.join(os.path.expanduser("~"), ".config", "copr")
        config = {}
        if not raw_config.read(filepath):
            raise exceptions.CoprNoConfException(
                "No configuration file '~/.config/copr' found. "
                "See man copr-cli for more information")
        try:
            for field in ["username", "login", "token", "copr_url"]:
                config[field] = raw_config.get("copr-cli", field, None)
        except ConfigParser.Error as err:
            raise exceptions.CoprConfigException(
                "Bad configuration file: {0}".format(err))
        return CoprClient(config=config)

    def _fetch(self, url, data=None, projectname=None, method=None,
               skip_auth=False, on_error_response=None):
        """ Fetch data from server,
        checks response and raises a CoprCliRequestException with nice error message
        or CoprCliUnknownResponseException in case of some some error.
        Otherwise return json object.

        :param url: formed url to fetch
        :param data: serialised data to send
        :param skip_auth: don't send auth credentials
        :param projectname: name of the copr project
        :param on_error_response: function to handle responses with bad status code
        """
        if method is None:
            method = "get"

        log.debug("Fetching url: {0}, for login: {1}".format(url, self.login))

        kwargs = {}
        if not skip_auth:
            kwargs["auth"] = (self.login, self.token)
        if data is not None:
            kwargs["data"] = data

        if method not in ["get", "post", "head", "delete", "put"]:
            raise Exception("Method {0} not allowed".format(method))

        #print("Url: {0}".format(url))
        #print(kwargs)
        response = requests.request(
            method=method.upper(),
            url=url,
            **kwargs
        )
        log.debug("raw response: {0}".format(response.text))

        if "<title>Sign in Coprs</title>" in response.text:
            raise exceptions.CoprRequestException("Invalid API token\n")

        if response.status_code > 299 and on_error_response is not None:
            return on_error_response(response)

        #TODO: better status code handling
        if response.status_code == 404:
            if projectname is None:
                raise exceptions.CoprRequestException(
                            "User {0} is unknown.\n".format(self.username))
            else:
                raise exceptions.CoprRequestException(
                            "Project {0}/{1} not found.\n".format(
                            self.username, projectname))

        if 400 <= response.status_code < 500:
            log.error("Bad request, raw response body: {0}".format(response.text))
        elif response.status_code >= 500:
            #import ipdb; ipdb.set_trace()
            log.error("Server error, raw response body: {0}".format(response.text))

        try:
            output = json.loads(response.text)
        except ValueError:
            #import ipdb; ipdb.set_trace()
            raise exceptions.CoprUnknownResponseException(
                        "Unknown response from the server.")
        if response.status_code != 200:
            raise exceptions.CoprRequestException(output["error"])

        if output is None:
            raise exceptions.CoprUnknownResponseException(
                        "No response from the server.")
        return output

    def get_build_status(self, build_id):
        url = "{0}/coprs/build_status/{1}/".format(
            self.api_url, build_id)

        response = self._fetch(url)
        return BuildStatusResponse(
            client=self, build_id=build_id, response=response)

    def get_build_details(self, build_id):
        url = "{0}/coprs/build/{1}/".format(
            self.api_url, build_id)

        response = self._fetch(url, skip_auth=True)
        return BuildDetailsResponse(self, response, build_id)

    def cancel_build(self, build_id):
        url = "{0}/coprs/cancel_build/{1}/".format(
            self.api_url, build_id)
        response = self._fetch(url, method="post")
        return CancelBuildResponse(self, response, build_id)

    def delete_project(self, projectname):
        """
            Delete the entire project
        """
        url = "{0}/coprs/{1}/{2}/delete/".format(
            self.api_url, self.username, projectname
        )
        response = self._fetch(
            url, data={"verify": "yes"}, method="post")
        return DeleteProjectResponse(self, response, projectname)

    def get_project_details(self, projectname):
        """
            Get project details
        """
        url = "{0}/coprs/{1}/{2}/detail/".format(
            self.api_url, self.username, projectname
        )

        response = self._fetch(url, skip_auth=True)
        return ProjectDetailsResponse(self, response, projectname)

    def create_project(
            self, projectname,
            description=None, instructions=None,
            chroots=None, repos=None, initial_pkgs=None
    ):
        """
            Create a new copr project
        """

        url = "{0}/coprs/{1}/new/".format(
            self.api_url, self.username)

        if type(repos) == list():
            repos = " ".join(repos)

        if type(initial_pkgs) == list():
            initial_pkgs = " ".join(initial_pkgs)

        data = {"name": projectname,
                "repos": repos,
                "initial_pkgs": initial_pkgs,
                "description": description,
                "instructions": instructions
                }
        for chroot in chroots:
            data[chroot] = "y"

        #def on bad_response()
        response = self._fetch(url, data=data, method="post")
        return CreateProjectResponse(
            self, response,
            name=projectname, description=description, instructions=instructions,
            repos=repos, chroots=chroots, initial_pkgs=initial_pkgs
        )

    def get_projects_list(self, username=None):
        """
            Get list of projects created by the user
        """
        url = "{0}/coprs/{1}/".format(
            self.api_url, username or self.username)
        response = self._fetch(url)
        return GetProjectsListResponse(self, response)

    def get_project_chroot_details(self, name, chroot):
        url = "{0}/coprs/{1}/{2}/detail/{3}/".format(
            self.api_url, self.username, name, chroot
        )
        response = self._fetch(url, skip_auth=True)
        return BaseResponse(self, response)

    def modify_project_chroot_details(self, projectname, chroot, pkgs=None):
        if pkgs is None:
            pkgs = []

        url = "{0}/coprs/{1}/{2}/modify/{3}/".format(
            self.api_url, self.username, projectname, chroot
        )
        data = {
            "buildroot_pkgs": " ".join(pkgs)
        }
        response = self._fetch(url, data=data, method="post")
        return BaseResponse(self, response)

    def modify_project(self, projectname, description=None,
                       instructions=None, repos=None):

        """
            Modifies main project settings
            :param projectname:
            :param description:
            :param instructions:
            :param repos:
            :return:
        """
        url = "{0}/coprs/{1}/{2}/modify/".format(
            self.api_url, self.username, projectname
        )
        data = {}
        if description:
            data["description"] = description
        if instructions:
            data["instructions"] = instructions
        if repos:
            data["repos"] = repos

        response = self._fetch(url, data=data, method="post")
        return ModifyProjectResponse(self, response, projectname, description,
                                     instructions, repos)

    def create_new_build(self, projectname, pkgs,
                         timeout=None, memory=None, chroots=None):
        """

            :param projectname: name of copr project (without user namespace)
            :param pkgs: list of packages to include in build

            :param timeout: ?? build timeout

            :param memory: amount of required memory for build process
            :param wait: if True function wait for packages to be build
            :param result:
            :param chroots:

        """

        url = "{0}/coprs/{1}/{2}/new_build/".format(
            self.api_url, self.username, projectname
        )
        data = {
            "pkgs": " ".join(pkgs),
            "memory_reqs": memory,
            "timeout": timeout
        }
        for chroot in chroots or []:
            data[chroot] = "y"

        response = self._fetch(url, data, method="post")
        return BuildRequestResponse(
            self, response,
            projectname, pkgs, memory, timeout, chroots)

    def search_projects(self, query):
        url = "{0}/coprs/search/{1}/".format(
            self.api_url, query
        )
        response = self._fetch(url, skip_auth=True)
        return SearchResponse(self, response, query)
