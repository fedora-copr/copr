# -*- coding: UTF-8 -*-
# pylint: disable=W1202

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import json
import sys
import os
import logging

import requests
import six

from six.moves import configparser
from requests_toolbelt.multipart.encoder import (MultipartEncoder,
                                                 MultipartEncoderMonitor)

# urlparse from six is not available on el7
# because it requires at least python-six-1.4.1
if sys.version_info[0] == 2:
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

if sys.version_info < (2, 7):
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
else:
    from logging import NullHandler

log = logging.getLogger(__name__)
log.addHandler(NullHandler())

from ..exceptions import CoprConfigException, CoprNoConfException, \
    CoprRequestException, \
    CoprUnknownResponseException

from .responses import ProjectHandle, \
    CoprResponse, BuildHandle, BaseHandle, ProjectChrootHandle

from .parsers import fabric_simple_fields_parser, ProjectListParser, \
    CommonMsgErrorOutParser, NewBuildListParser, ProjectChrootsParser, \
    ProjectDetailsFieldsParser

from ..util import UnicodeMixin

# TODO: add deco to check that login/token are provided
# and  raise correct error
# """ "No configuration file '~/.config/copr' found. "
# "see documentation at /usr/share/doc/python-copr/ "
# """
# or
# """
# "No api login and/or api token are provided"
#    "See man copr-cli for more information")
# """


class CoprClient(UnicodeMixin):
    """ Main interface to the copr service

    :ivar unicode username: username used by default for all requests
    :ivar unicode login: user login, used for identification
    :ivar unicode token: copr api token
    :ivar unicode copr_url: used as copr projects root

    Could be created:
        - directly
        - using static method :py:meth:`CoprClient.create_from_file_config`

    """

    def __init__(self, username=None, login=None, token=None, copr_url=None,
                 no_config=False):
        """
            :param unicode username: username used by default for all requests
            :param unicode login: user login, used for identification
            :param unicode token: copr api token
            :param unicode copr_url: used as copr projects root
            :param bool no_config: helper flag to indicate that no config was provided
        """

        self.token = token
        self.login = login
        self.username = username
        self.copr_url = copr_url or "http://copr.fedoraproject.org/"

        self.no_config = no_config

    def __unicode__(self):
        return (
            u"<Copr client. username: {0}, api url: {1}, login presents: {2}, token presents: {3}>"
            .format(self.username, self.api_url, bool(self.login), bool(self.token))
        )

    @property
    def api_url(self):
        """
            Url to API endpoint
        """
        return "{0}/api".format(self.copr_url)

    @staticmethod
    def create_from_file_config(filepath=None, ignore_error=False):
        """
        Creates Copr client using the information from the config file.

        :param filepath: specifies config location,
            default: "~/.config/copr"
        :type filepath: `str`
        :param bool ignore_error: When true creates default Client
            without credentionals

        :rtype: :py:class:`~.client.CoprClient`

        """

        raw_config = configparser.ConfigParser()
        if not filepath:
            filepath = os.path.join(os.path.expanduser("~"), ".config", "copr")
        config = {}
        if not raw_config.read(filepath):
            log.warning(
                "No configuration file '~/.config/copr' found. "
                "See man copr-cli for more information")
            config["no_config"] = True
            if not ignore_error:
                raise CoprNoConfException()
        else:
            try:
                for field in ["username", "login", "token", "copr_url"]:
                    if six.PY3:
                        config[field] = raw_config["copr-cli"].get(field, None)
                    else:
                        config[field] = raw_config.get("copr-cli", field, None)

            except configparser.Error as err:
                if not ignore_error:
                    raise CoprConfigException(
                        "Bad configuration file: {0}".format(err))
        return CoprClient(**config)

    def _fetch(self, url, data=None, username=None, method=None,
               skip_auth=False, on_error_response=None, headers=None):
        """ Fetches data from server,
        checks response and raises a CoprRequestException with nice error message
        or CoprUnknownResponseException in case of some some error. \n
        Otherwise return unpacked json object.

            :param url: formed url to fetch
            :param data: [optional] serialised data to send
            :param skip_auth: [optional] don't send auth credentials
            :param username: [optional] use alternative username
            :param on_error_response: [optional] function to handle responses
                with bad status code
            :param headers: [optional] custom request headers

            :return: deserialized response
            :rtype: dict
        """

        if method is None:
            method = "get"

        if not username:
            username = self.username

        log.debug("Fetching url: {0}, for login: {1}".format(url, self.login))
        kwargs = {}
        if not skip_auth:
            kwargs["auth"] = (self.login, self.token)
        if data is not None:
            kwargs["data"] = data
        if headers is not None:
            kwargs["headers"] = headers

        if method not in ["get", "post", "head", "delete", "put"]:
            raise Exception("Method {0} not allowed".format(method))

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                **kwargs
            )
            log.debug("raw response: {0}".format(response.text))
        except requests.ConnectionError as e:
            raise CoprRequestException(e)

        if "<title>Sign in Copr</title>" in response.text:
            raise CoprRequestException("Invalid API token\n")

        if response.status_code > 299 and on_error_response is not None:
            return on_error_response(response)

        if response.status_code == 404:
            log.error("Bad request, URL not found: {0}".
                      format(url))
        elif 400 <= response.status_code < 500:
            log.error("Bad request, raw response body: {0}".
                      format(response.text))
        elif response.status_code >= 500:
            log.error("Server error, raw response body: {0}".
                      format(response.text))

        try:
            output = json.loads(response.text)
        except ValueError:
            raise CoprUnknownResponseException(
                "Unknown response from the server. Code: {0}, raw response:"
                " \n {1}".format(response.status_code, response.text))
        if response.status_code != 200:
            raise CoprRequestException(output["error"])

        if output is None:
            raise CoprUnknownResponseException("No response from the server.")
        return output

    def get_build_details(self, build_id, projectname=None, username=None):
        """ Returns build details.

            :param build_id: Build identifier
            :type build_id: int

            :param projectname: [optional] Copr project name
            :param username: [optional] Copr project owner

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **handle:** :py:class:`~.responses.BuildHandle`
                - text fields: "project", "owner", "status", "results",
                "submitted_on", "started_on", "ended_on",
                "built_pkgs", "src_pkg", "src_version"


        """

        url = "{0}/coprs/build/{1}/".format(
            self.api_url, build_id)

        data = self._fetch(url, skip_auth=True)
        response = CoprResponse(
            client=self,
            method="get_build_details",
            data=data,
            parsers=[
                CommonMsgErrorOutParser,
                fabric_simple_fields_parser(
                    [
                        "project", "owner", "status", "results", "results_by_chroot",
                        "submitted_on", "started_on", "ended_on",
                        "built_pkgs", "src_pkg", "src_version",
                    ],  # TODO: convert unix time
                    "BuildDetailsParser"
                )
            ]
        )
        response.handle = BuildHandle(
            self, response=response, build_id=build_id,
            projectname=getattr(response, "project", projectname),
            username=getattr(response, "owner", username)
        )
        return response

    def cancel_build(self, build_id, projectname=None, username=None):
        """ Cancels build.
            Auth required.
            If build can't be canceled do nothing.

            :param build_id: Build identifier
            :type build_id: int

            :param projectname: [optional] Copr project name
            :param username: [optional] Copr project owner

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **handle:** :py:class:`~.responses.BuildHandle`
                - text fields: "status"
        """

        url = "{0}/coprs/cancel_build/{1}/".format(
            self.api_url, build_id)

        data = self._fetch(url, skip_auth=False, method='post')
        response = CoprResponse(
            client=self,
            method="cancel_build",
            data=data,
            parsers=[
                fabric_simple_fields_parser(["status", "output", "error"]),
            ]
        )
        response.handle = BuildHandle(
            self, response=response, build_id=build_id,
            projectname=projectname, username=username
        )
        return response

    def create_new_build(self, projectname, pkgs, username=None,
                         timeout=None, memory=None, chroots=None,
                         progress_callback=None):
        """ Creates new build

            :param projectname: name of Copr project (without user namespace)
            :param pkgs: list of packages to include in build
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        if not username:
            username = self.username
        data = {
            "memory_reqs": memory,
            "timeout": timeout
        }

        if urlparse(pkgs[0]).scheme != "":
            api_endpoint = "new_build"
            data["pkgs"] = " ".join(pkgs)
        else:
            try:
                api_endpoint = "new_build_upload"
                f = open(pkgs[0], "rb")
                data["pkgs"] = (os.path.basename(f.name), f, "application/x-rpm")
            except IOError as e:
                raise CoprRequestException(e)

        url = "{0}/coprs/{1}/{2}/{3}/".format(
            self.api_url, username, projectname, api_endpoint
        )

        for chroot in chroots or []:
            data[chroot] = "y"

        m = MultipartEncoder(data)

        callback = progress_callback or (lambda x: x)

        monit = MultipartEncoderMonitor(m, callback)
        data = self._fetch(url, monit, method="post",
                           headers={'Content-Type': monit.content_type})

        response = CoprResponse(
            client=self,
            method="cancel_build",
            data=data,
            request_kwargs={
                "projectname": projectname,
                "username": username
            },
            parsers=[
                CommonMsgErrorOutParser,
                NewBuildListParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=username)

        return response


    def create_new_build_pypi(self, projectname, pypi_package_name, pypi_package_version=None,
                         python_versions=[3, 2], username=None, timeout=None, memory=None,
                         chroots=None, progress_callback=None):
        """ Creates new build from PyPI

            :param projectname: name of Copr project (without user namespace)
            :param pypi_package_name: PyPI package name
            :param pypi_package_vesion: [optional] PyPI package version (None means "latest")
            :param python_versions: [optional] list of python versions to build for
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        if not username:
            username = self.username

        data = {
            "memory_reqs": memory,
            "timeout": timeout,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "python_versions": [str(version) for version in python_versions],
            "source_type": "pypi",
        }

        api_endpoint = "new_build_pypi"

        url = "{0}/coprs/{1}/{2}/{3}/".format(
            self.api_url, username, projectname, api_endpoint
        )

        for chroot in chroots or []:
            data[chroot] = "y"

        data = self._fetch(url, data, method="post")

        response = CoprResponse(
            client=self,
            method="cancel_build",
            data=data,
            request_kwargs={
                "projectname": projectname,
                "username": username
            },
            parsers=[
                CommonMsgErrorOutParser,
                NewBuildListParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=username)

        return response

    def create_new_build_tito(self, projectname, git_url, git_dir=None, git_branch=None, tito_test=None, username=None,
                              timeout=None, memory=None, chroots=None, progress_callback=None):
        """ Creates new build from PyPI

            :param projectname: name of Copr project (without user namespace)
            :param git_url: url to Git code which is able to build via Tito
            :param git_dir: [optional] path to directory containing .spec file
            :param git_branch: [optional] git branch
            :param tito_test: [optional] build the last commit instead of the last release tag
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        data = {
            "memory_reqs": memory,
            "timeout": timeout,
            "git_url": git_url,
            "git_directory": git_dir,  # @FIXME
            "git_branch": git_branch,
            "tito_test": tito_test,
            "source_type": "git_and_tito",
        }
        api_endpoint = "new_build_tito"
        return self.process_creating_new_build(projectname, data, api_endpoint, username, chroots)

    def create_new_build_mock(self, projectname, scm_url, spec, scm_type="git", scm_branch=None, username=None,
                              timeout=None, memory=None, chroots=None, progress_callback=None):
        """ Creates new build from PyPI

            :param projectname: name of Copr project (without user namespace)
            :param scm_url: url to a project versioned by Git or SVN
            :param spec: relative path from SCM root to .spec file
            :param scm_type: possible values are "git" and "svn"
            :param scm_branch: [optional] Git or SVN branch
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        data = {
            "memory_reqs": memory,
            "timeout": timeout,
            "scm_type": scm_type,
            "scm_url": scm_url,
            "scm_branch": scm_branch,
            "spec": spec,
            "source_type": "mock_scm",
        }
        api_endpoint = "new_build_mock"
        return self.process_creating_new_build(projectname, data, api_endpoint, username, chroots)

    def process_creating_new_build(self, projectname, data, api_endpoint, username=None, chroots=None):
        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/{3}/".format(
            self.api_url, username, projectname, api_endpoint
        )

        for chroot in chroots or []:
            data[chroot] = "y"

        data = self._fetch(url, data, method="post")

        response = CoprResponse(
            client=self,
            method="cancel_build",
            data=data,
            request_kwargs={
                "projectname": projectname,
                "username": username
            },
            parsers=[
                CommonMsgErrorOutParser,
                NewBuildListParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=username)

        return response


    def get_project_details(self, projectname, username=None):
        """ Returns project details

            :param projectname: Copr projectname
            :param username: [optional] use alternative username

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - text fields: "description", "instructions", "last_modified",
                "name"

                - **chroots**: list of
                  :py:class:`~.responses.ProjectChrootWrapper`
        """
        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/detail/".format(
            self.api_url, username, projectname
        )

        data = self._fetch(url, skip_auth=True)
        # return ProjectDetailsResponse(self, response, projectname, username)

        response = CoprResponse(
            client=self,
            method="get_project_details",
            data=data,
            request_kwargs={
                "projectname": projectname,
                "username": username
            },
            parsers=[
                ProjectChrootsParser,
                ProjectDetailsFieldsParser,
            ]
        )
        response.handle = ProjectHandle(client=self, response=response,
                                        projectname=projectname,
                                        username=username)
        return response

    def delete_project(self, projectname, username=None):
        """ Deletes the entire project.
            Auth required.

            :param projectname: Copr projectname
            :param username: [optional] use alternative username

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - text fields: "message"
        """

        if not username:
            username = self.username
        url = "{0}/coprs/{1}/{2}/delete/".format(
            self.api_url, username, projectname
        )

        data = self._fetch(
            url, data={"verify": "yes"}, method="post")

        response = CoprResponse(
            client=self,
            method="delete_project",
            data=data,
            parsers=[
                CommonMsgErrorOutParser,
            ]
        )
        response.handle = ProjectHandle(client=self, response=response,
                                        projectname=projectname,
                                        username=username)
        return response

    def create_project(
            self, username, projectname, chroots,
            description=None, instructions=None,
            repos=None, initial_pkgs=None
    ):
        """ Creates a new copr project
            Auth required.

            :param projectname: User or group name
            :param projectname: Copr project name
            :param chroots: List of target chroots
            :param description: [optional] Project description
            :param instructions: [optional] Instructions for end users

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.ProjectHandle`
                - text fields: "message"
        """

        if not username:
            username = self.username

        url = "{0}/coprs/{1}/new/".format(
            self.api_url, username)

        if not chroots:
            raise Exception("You should provide chroots")

        if not isinstance(chroots, list):
            chroots = [chroots]

        if isinstance(repos, list):
            repos = " ".join(repos)

        if isinstance(initial_pkgs, list):
            initial_pkgs = " ".join(initial_pkgs)

        request_data = {
            "name": projectname,
            "repos": repos,
            "initial_pkgs": initial_pkgs,
            "description": description,
            "instructions": instructions
        }
        for chroot in chroots:
            request_data[chroot] = "y"

        # TODO: def on bad_response()
        result_data = self._fetch(url, data=request_data, method="post")

        response = CoprResponse(
            client=self,
            method="create_project",
            data=result_data,
            parsers=[
                CommonMsgErrorOutParser,
            ]
        )
        response.handle = ProjectHandle(client=self, response=response,
                                        projectname=projectname)
        return response

    def modify_project(self, projectname, username=None,
                       description=None, instructions=None,
                       repos=None, disable_createrepo=None):
        """ Modifies main project configuration.
            Auth required.

            :param projectname: Copr project name
            :param username: [optional] use alternative username
            :param description: [optional] project description
            :param instructions: [optional] instructions for end users
            :param repos: [optional] list of additional repos to be used during
                the build process

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.ProjectHandle`
                - text fields: "buildroot_pkgs"
        """

        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/modify/".format(
            self.api_url, username, projectname
        )
        data = {}
        if description:
            data["description"] = description
        if instructions:
            data["instructions"] = instructions
        if repos:
            data["repos"] = repos
        if disable_createrepo:
            data["disable_createrepo"] = disable_createrepo

        result_data = self._fetch(url, data=data, method="post")

        response = CoprResponse(
            client=self,
            method="modify_project",
            data=result_data,
            parsers=[
                CommonMsgErrorOutParser,
                ProjectDetailsFieldsParser,
                fabric_simple_fields_parser(["buildroot_pkgs"])
            ]
        )
        response.handle = ProjectHandle(client=self, response=response,
                                        projectname=projectname)
        return response

    def get_projects_list(self, username=None):
        """ Returns list of projects created by the user

            :param username: [optional] use alternative username


            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **projects_list**: list of
                  :py:class:`~.responses.ProjectWrapper`
        """
        if not username:
            username = self.username

        url = "{0}/coprs/{1}/".format(
            self.api_url, username)
        data = self._fetch(url)
        response = CoprResponse(
            client=self,
            method="get_projects_list",
            data=data,
            parsers=[
                CommonMsgErrorOutParser,
                ProjectListParser,
            ]
        )
        response.handle = BaseHandle(client=self, username=username,
                                     response=response)
        return response

    def get_project_chroot_details(self, projectname,
                                   chrootname, username=None):
        """ Returns details of chroot used in project

            :param projectname: Copr project name
            :param chrootname: chroot name

            :param username: [optional] use alternative username

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.ProjectChrootHandle`
                - text fields: "buildroot_pkgs"
        """
        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/detail/{3}/".format(
            self.api_url, username, projectname, chrootname
        )
        data = self._fetch(url, skip_auth=True)
        response = CoprResponse(
            client=self,
            method="get_project_chroot_details",
            data=data,
            parsers=[
                fabric_simple_fields_parser(
                    ["buildroot_pkgs", "output", "error"],
                    "BuildDetailsParser"
                )
            ]
        )
        response.handle = ProjectChrootHandle(
            client=self, chrootname=chrootname, username=username,
            projectname=projectname, response=response
        )
        return response

    def modify_project_chroot_details(self, projectname, chrootname,
                                      pkgs=None, username=None):
        """ Modifies chroot used in project

            :param projectname: Copr project name
            :param chrootname: chroot name

            :param username: [optional] use alternative username

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.ProjectChrootHandle`
                - text fields: "buildroot_pkgs"

        """
        if pkgs is None:
            pkgs = []

        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/modify/{3}/".format(
            self.api_url, username, projectname, chrootname
        )
        data = {
            "buildroot_pkgs": " ".join(pkgs)
        }
        data = self._fetch(url, data=data, method="post")

        response = CoprResponse(
            client=self,
            method="modify_project_chroot_details",
            data=data,
            parsers=[
                fabric_simple_fields_parser(
                    ["buildroot_pkgs", "output", "error"],
                    "BuildDetailsParser"
                )
            ]
        )
        response.handle = ProjectChrootHandle(
            client=self, chrootname=chrootname, username=username,
            projectname=projectname, response=response
        )
        return response

    def search_projects(self, query):
        """ Search projects by substring

            :param query: substring to search

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **projects_list**: list of
                  :py:class:`~.responses.ProjectWrapper`
        """
        url = "{0}/coprs/search/{1}/".format(
            self.api_url, query
        )
        data = self._fetch(url, skip_auth=True)

        response = CoprResponse(
            client=self,
            method="search_projects",
            data=data,
            parsers=[
                CommonMsgErrorOutParser,
                ProjectListParser
            ]
        )
        response.handle = BaseHandle(client=self, response=response)
        return response
