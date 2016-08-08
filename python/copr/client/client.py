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
    CoprResponse, BuildHandle, BaseHandle, ProjectChrootHandle, PackageHandle

from .parsers import fabric_simple_fields_parser, ProjectListParser, \
    CommonMsgErrorOutParser, NewBuildListParser, ProjectChrootsParser, \
    ProjectDetailsFieldsParser, PackageListParser, PackageParser

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


SOURCE_TYPE_SRPM_LINK = 'srpm_link'
SOURCE_TYPE_SRPM_UPLOAD = 'srpm_upload'
SOURCE_TYPE_GIT_AND_TITO = 'git_and_tito'
SOURCE_TYPE_MOCK_SCM = 'mock_scm'
SOURCE_TYPE_PYPI = 'pypi'
SOURCE_TYPE_RUBYGEMS = 'rubygems'

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

        try:
            exists = raw_config.read(filepath)
        except configparser.Error as e:
            raise CoprConfigException()

        if not exists:
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
               skip_auth=False, on_error_response=None, headers=None, params=None):
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
            :param params: [optional] data for GET requests

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
        if params is not None:
            kwargs["params"] = params

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
            log.error(e)
            raise CoprRequestException("Connection error {} {}".format(method.upper(), url))

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

    #########################################################
    ###                    Build actions                  ###
    #########################################################

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
                         background=False, progress_callback=None):
        """ Creates new build

            :param projectname: name of Copr project (without user namespace)
            :param pkgs: list of packages to include in build
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param background: [optional] mark the build as a background job.
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
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

        return self.process_creating_new_build(projectname, data, api_endpoint, username, chroots, background=background,
                                               progress_callback=progress_callback, multipart=True)

    def create_new_build_pypi(self, projectname, pypi_package_name, pypi_package_version=None,
                         python_versions=[3, 2], username=None, timeout=None, memory=None,
                         chroots=None, background=False, progress_callback=None):
        """ Creates new build from PyPI

            :param projectname: name of Copr project (without user namespace)
            :param pypi_package_name: PyPI package name
            :param pypi_package_vesion: [optional] PyPI package version (None means "latest")
            :param python_versions: [optional] list of python versions to build for
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param background: [optional] mark the build as a background job.
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        data = {
            "memory_reqs": memory,
            "timeout": timeout,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "python_versions": [str(version) for version in python_versions],
        }
        api_endpoint = "new_build_pypi"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)

    def create_new_build_tito(self, projectname, git_url, git_dir=None, git_branch=None, tito_test=None, username=None,
                              timeout=None, memory=None, chroots=None, background=False, progress_callback=None):
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
            :param background: [optional] mark the build as a background job.
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
        }
        api_endpoint = "new_build_tito"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)

    def create_new_build_mock(self, projectname, scm_url, spec, scm_type="git", scm_branch=None, username=None,
                              timeout=None, memory=None, chroots=None, background=False, progress_callback=None):
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
            :param background: [optional] mark the build as a background job.
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
        }
        api_endpoint = "new_build_mock"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)

    def create_new_build_rubygems(self, projectname, gem_name, username=None,
                              timeout=None, memory=None, chroots=None, background=False, progress_callback=None):
        """ Creates new build from RubyGems.org

            :param projectname: name of Copr project (without user namespace)
            :param gem_name: name of the gem located on rubygems.org
            :param username: [optional] use alternative username
            :param timeout: [optional] build timeout
            :param memory: [optional] amount of required memory for build process
            :param chroots: [optional] build only with given chroots
            :param background: [optional] mark the build as a background job.
            :param progress_callback: [optional] a function that received a
            MultipartEncoderMonitor instance for each chunck of uploaded data

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **builds_list**: list of :py:class:`~.responses.BuildWrapper`
        """
        data = {
            "memory_reqs": memory,
            "timeout": timeout,
            "gem_name": gem_name,
        }
        api_endpoint = "new_build_rubygems"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)

    def process_creating_new_build(self, projectname, data, api_endpoint, username=None, chroots=None,
                                   background=False, progress_callback=None, multipart=False):
        if not username:
            username = self.username

        url = "{0}/coprs/{1}/{2}/{3}/".format(
            self.api_url, username, projectname, api_endpoint
        )

        if background:
            data["background"] = "y"

        for chroot in chroots or []:
            data[chroot] = "y"

        if not multipart:
            data = self._fetch(url, data, method="post")
        else:
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

    #########################################################
    ###                   Package actions                 ###
    #########################################################

    def get_package_edit_url(self, ownername, projectname, package_name, source_type):
        return "{0}/coprs/{1}/{2}/package/{3}/edit/{4}/".format(
            self.api_url, ownername or self.username, projectname, package_name, source_type
        )

    def get_package_add_url(self, ownername, projectname, source_type):
        return "{0}/coprs/{1}/{2}/package/add/{3}/".format(
            self.api_url, ownername or self.username, projectname, source_type
        )

    def get_package_delete_url(self, ownername, projectname, package_name):
        return "{0}/coprs/{1}/{2}/package/{3}/delete/".format(
            self.api_url, ownername or self.username, projectname, package_name
        )

    def edit_package_tito(self, package_name, projectname, git_url, git_dir=None, git_branch=None, tito_test=None, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_GIT_AND_TITO)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "git_url": git_url,
            "git_directory": git_dir,
            "git_branch": git_branch,
            "tito_test": 'y' if tito_test else '', # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better
            "webhook_rebuild": 'y' if webhook_rebuild else '', # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better
        })
        return response

    def add_package_tito(self, package_name, projectname, git_url, git_dir=None, git_branch=None, tito_test=None, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_GIT_AND_TITO)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "git_url": git_url,
            "git_directory": git_dir,
            "git_branch": git_branch,
            "tito_test": 'y' if tito_test else '', # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better
            "webhook_rebuild": 'y' if webhook_rebuild else '', # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better
        })
        return response

    def edit_package_pypi(self, package_name, projectname, pypi_package_name, pypi_package_version, python_versions=[3, 2], ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_PYPI)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "python_versions": python_versions,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def add_package_pypi(self, package_name, projectname, pypi_package_name, pypi_package_version, python_versions=[3, 2], ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_PYPI)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "python_versions": python_versions,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def edit_package_mockscm(self, package_name, projectname, scm_type, scm_url, scm_branch, spec, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_MOCK_SCM)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "scm_type": scm_type,
            "scm_url": scm_url,
            "scm_branch": scm_branch,
            "spec": spec,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def add_package_mockscm(self, package_name, projectname, scm_type, scm_url, scm_branch, spec, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_MOCK_SCM)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "scm_type": scm_type,
            "scm_url": scm_url,
            "scm_branch": scm_branch,
            "spec": spec,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def edit_package_rubygems(self, package_name, projectname, gem_name, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_RUBYGEMS)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "gem_name": gem_name,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def add_package_rubygems(self, package_name, projectname, gem_name, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_RUBYGEMS)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "gem_name": gem_name,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def process_package_action(self, request_url, ownername, projectname, data):
        if not ownername:
            ownername = self.username

        resp_data = self._fetch(request_url, data, method="post")

        response = CoprResponse(
            client=self,
            method="post",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname,
            username=ownername
        )

        return response

    def get_packages_list(self, projectname, with_latest_build=False, with_latest_succeeded_build=False, with_all_builds=False, ownername=None):
        """Returns list of packages for the given copr."""

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/package/list/".format(
            self.api_url, ownername, projectname
        )

        resp_data = self._fetch(url, params={
            "with_latest_build": 'y' if with_latest_build else '',
            "with_latest_succeeded_build": 'y' if with_latest_succeeded_build else '',
            "with_all_builds": 'y' if with_all_builds else '',
        })
        response = CoprResponse(
            client=self,
            method="get",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
                PackageListParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname,
            username=ownername
        )

        return response

    def get_package(self, projectname, pkg_name, with_latest_build=False, with_latest_succeeded_build=False, with_all_builds=False, ownername=None):
        """Returns single package if pkg_name."""

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/package/get/{3}/".format(
            self.api_url, ownername, projectname, pkg_name
        )

        resp_data = self._fetch(url, params={
            "with_latest_build": 'y' if with_latest_build else '',
            "with_latest_succeeded_build": 'y' if with_latest_succeeded_build else '',
            "with_all_builds": 'y' if with_all_builds else '',
        })
        response = CoprResponse(
            client=self,
            method="get",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
                PackageParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=ownername
        )

        return response

    def delete_package(self, projectname, pkg_name, ownername=None):
        """Deletes the given package."""

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/package/delete/{3}/".format(
            self.api_url, ownername, projectname, pkg_name
        )

        resp_data = self._fetch(url, method="post")
        response = CoprResponse(
            client=self,
            method="post",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=ownername
        )

        return response

    def reset_package(self, projectname, pkg_name, ownername=None):
        """Resets default source of the given package."""

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/package/reset/{3}/".format(
            self.api_url, ownername, projectname, pkg_name
        )

        resp_data = self._fetch(url, method="post")
        response = CoprResponse(
            client=self,
            method="post",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=ownername
        )

        return response

    def build_package(self, projectname, pkg_name, ownername=None, chroots=None, timeout=None):
        """Builds the package from its default source."""

        if not ownername:
            ownername = self.username

        request_url = "{0}/coprs/{1}/{2}/package/build/{3}/".format(
            self.api_url, ownername, projectname, pkg_name
        )

        data = {}
        for chroot in chroots or []:
            data[chroot] = "y"
        if timeout:
            data["timeout"] = timeout

        resp_data = self._fetch(request_url, data, method="post")
        response = CoprResponse(
            client=self,
            method="post",
            data=resp_data,
            request_kwargs={
                "projectname": projectname,
                "username": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
                NewBuildListParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname, username=ownername
        )

        return response

    #########################################################
    ###                   Project actions                 ###
    #########################################################

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

    def fork_project(self, source, projectname, username=None, confirm=False):
        """ Fork the project and builds in it
        Auth required.

        :param source: source Copr name or full_name
        :param projectname: destination Copr projectname
        :param username: [optional] use alternative username as owner of forked project
        :param confirm: [optional] need to pass True when forking into existing project

        :return: :py:class:`~.responses.CoprResponse`
        with additional fields:

        - text fields: "message"
        """
        if not username:
            username = self.username
        url = "{0}/coprs/{1}/fork/".format(
            self.api_url, source
        )

        post_data = {
            "name": projectname,
            "owner": username,
            "source": source,
        }
        if confirm:
            post_data["confirm"] = confirm
        data = self._fetch(url, data=post_data, method="post")

        response = CoprResponse(
            client=self,
            method="fork_project",
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
            repos=None, initial_pkgs=None, disable_createrepo=None, unlisted_on_hp=False, enable_net=True, persistent=False
    ):
        """ Creates a new copr project
            Auth required.

            :param projectname: User or group name
            :param projectname: Copr project name
            :param chroots: List of target chroots
            :param description: [optional] Project description
            :param instructions: [optional] Instructions for end users
            :param disable_createrepo: [optional] disables automatic repo meta-data regeneration, "true"/"false" string
            :param unlisted_on_hp: [optional] Project will not be shown on COPR HP
            :param enable_net: [optional] If builder can access net for builds in this project
            :param persistent: [optional] If builds and the project are undeletable

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
            "instructions": instructions,
            "disable_createrepo": disable_createrepo,
            "unlisted_on_hp": "y" if unlisted_on_hp else "",
            "build_enable_net": "y" if enable_net else "",
            "persistent": "y" if persistent else "",
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
                       repos=None, disable_createrepo=None, unlisted_on_hp=None, enable_net=None):
        """ Modifies main project configuration.
            Auth required.

            :param projectname: Copr project name
            :param username: [optional] use alternative username
            :param description: [optional] project description
            :param instructions: [optional] instructions for end users
            :param repos: [optional] list of additional repos to be used during
                the build process
            :param repos: [optional] list of additional repos to be used during
            :param disable_createrepo: [optional] disables automatic repo meta-data regeneration
            :param unlisted_on_hp: [optional] Project will not be shown on COPR HP
            :param enable_net: [optional] If builder can access net for builds in this project

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
        if unlisted_on_hp != None:
            data["unlisted_on_hp"] = "y" if unlisted_on_hp else ""
        if enable_net != None:
            data["build_enable_net"] = "y" if enable_net else ""

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
