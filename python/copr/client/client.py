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
import io
import warnings

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
    ProjectDetailsFieldsParser, PackageListParser, PackageParser, \
    BuildConfigParser, CoprChrootParser

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
SOURCE_TYPE_SCM = 'scm'
SOURCE_TYPE_CUSTOM = 'custom'

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
        self.copr_url = copr_url or "https://copr.fedorainfracloud.org/"

        self.no_config = no_config
        warnings.warn("You are using Copr's deprecated APIv1. "
                      "Please migrate to APIv3. "
                      "See https://fedora-copr.github.io/posts/EOL-APIv1-APIv2",
                      DeprecationWarning)

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

    def new_webhook_secret(self, coprname, ownername=None):
        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/{3}/".format(
            self.api_url, ownername, coprname, 'new_webhook_secret')

        data = self._fetch(url, method="post")

        response = CoprResponse(
            client=self,
            method="new_webhook_secret",
            data=data,
            parsers=[
                fabric_simple_fields_parser(["status", "output", "error", "message"]),
            ]
        )
        return response

    def authentication_check(self):
        url = "{0}/auth_check/".format(self.api_url)

        try:
            kwargs = {}
            kwargs["auth"] = (self.login, self.token)

            response = requests.request(
                method="POST",
                url=url,
                **kwargs
            )

            log.debug("raw response: {0}".format(response.text))

        except requests.ConnectionError as e:
            log.error(e)
            raise CoprRequestException("Connection error POST {0}".format(url))

        if not response.status_code in [200, 404]:
            try:
                output = json.loads(response.text)
            except ValueError:
                raise CoprUnknownResponseException(
                    "Unknown response from the server. Code: {0}, raw response:"
                    " \n {1}".format(response.status_code, response.text))
            raise CoprRequestException(output["error"])


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
            if type(data) not in [MultipartEncoder, MultipartEncoderMonitor]:
                data["username"] = username
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
            raise CoprRequestException("Connection error {0} {1}".format(method.upper(), url))

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

    def delete_build(self, build_id):
        """ Deletes build.
            Auth required.
            If build can't be deleted, return an error.

            :param build_id: Build identifier
            :type build_id: int

            :return: :py:class:`~.responses.CoprResponse` with additional fields:

                - **handle:** :py:class:`~.responses.BuildHandle`
                - text fields: "status"
        """

        url = "{0}/coprs/delete_build/{1}/".format(self.api_url, build_id)

        data = self._fetch(url, skip_auth=False, method='post')
        response = CoprResponse(
            client=self,
            method="delete_build",
            data=data,
            parsers=[
                fabric_simple_fields_parser(["status", "output", "error"]),
            ]
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
                              spec_template="", python_versions=[3, 2], username=None, timeout=None,
                              memory=None, chroots=None, background=False, progress_callback=None):
        """ Creates new build from PyPI

            :param projectname: name of Copr project (without user namespace)
            :param pypi_package_name: PyPI package name
            :param pypi_package_vesion: [optional] PyPI package version (None means "latest")
            :param spec_template: [optional] what spec template to use
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
            "spec_template": spec_template,
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
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)

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
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)

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

    def create_new_build_scm(self, projectname, clone_url, committish='', subdirectory='', spec='',
                             scm_type='git', srpm_build_method='rpkg', username=None, timeout=None,
                             memory=None, chroots=None, background=False, progress_callback=None):
        """ Creates new build from SCM

            :param projectname: name of Copr project (without user namespace)
            :param clone_url: url to a project versioned by Git or SVN
            :param committish [optional]: name of a branch, tag, or a git hash
            :param subdirectory [optional]: repo subdirectory with package content
            :param spec [optional]: path to spec file, relative to 'subdirectory'
            :param scm_type [optional]: "git" or "svn"
            :param srpm_build_method [optional]: tool to build srpm with. One of:
                "rpkg", "tito", "tito_test", "make_srpm"
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
            "clone_url": clone_url,
            "committish": committish,
            "subdirectory": subdirectory,
            "spec": spec,
            "scm_type": scm_type,
            "srpm_build_method": srpm_build_method,
        }
        api_endpoint = "new_build_scm"
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


    def create_new_build_custom(self, projectname,
            script, script_chroot=None, script_builddeps=None,
            script_resultdir=None,
            username=None, timeout=None, memory=None, chroots=None,
            background=False, progress_callback=None):
        """ Creates new build with Custom source build method.

            :param projectname: name of Copr project (without user namespace)
            :param script: script to execute to generate sources
            :param script_chroot: [optional] what chroot to use to generate
                sources (defaults to fedora-latest-x86_64)
            :param script_builddeps: [optional] list of script's dependencies
            :param script_resultdir: [optional] where script generates results
                (relative to cwd)
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
            "script": script,
            "chroot": script_chroot,
            "builddeps": script_builddeps,
            "resultdir": script_resultdir,
        }

        api_endpoint = "new_build_custom"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)


    def create_new_build_distgit(self, projectname, clone_url, branch=None, username=None,
                              timeout=None, memory=None, chroots=None, background=False, progress_callback=None):
        """ Creates new build from a dist-git repository

            :param projectname: name of Copr project (without user namespace)
            :param clone_url: url of the distgit repository to be cloned
            :param branch: [optional] branch in the repository to be checked out
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
            "clone_url": clone_url,
            "branch": branch,
        }
        api_endpoint = "new_build_distgit"
        return self.process_creating_new_build(projectname, data, api_endpoint, username,
                                               chroots, background=background)

    def process_creating_new_build(self, projectname, data, api_endpoint, username=None, chroots=None,
                                   background=False, progress_callback=None, multipart=False):
        if not username:
            username = self.username
        data["username"] = self.username

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
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_GIT_AND_TITO)
        data = {
            "package_name": package_name,
            "git_url": git_url,
            "git_directory": git_dir,
            "git_branch": git_branch,
            "tito_test": 'y' if tito_test else '', # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else '' # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_tito(self, package_name, projectname, git_url, git_dir=None, git_branch=None, tito_test=None, ownername=None, webhook_rebuild=None):
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)
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

    def edit_package_pypi(self, package_name, projectname, pypi_package_name, pypi_package_version,
                          spec_template="", python_versions=[3, 2], ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_PYPI)
        data = {
            "package_name": package_name,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "spec_template": spec_template,
            "python_versions": python_versions,
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else '' # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_pypi(self, package_name, projectname, pypi_package_name, pypi_package_version,
                         spec_template="", python_versions=[3, 2], ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_PYPI)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "spec_template": spec_template,
            "python_versions": python_versions,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def edit_package_mockscm(self, package_name, projectname, scm_type, scm_url, scm_branch, spec, ownername=None, webhook_rebuild=None):
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_MOCK_SCM)
        data = {
            "package_name": package_name,
            "scm_type": scm_type,
            "scm_url": scm_url,
            "scm_branch": scm_branch,
            "spec": spec,
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else '' # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_mockscm(self, package_name, projectname, scm_type, scm_url, scm_branch, spec, ownername=None, webhook_rebuild=None):
        print('Deprecated method. Use generic "scm" methods instead.', file=sys.stderr)
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

    def edit_package_scm(self, package_name, projectname, clone_url, committish='', subdirectory='', spec='',
                         scm_type='git', srpm_build_method='rpkg', ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_SCM)
        data = {
            "package_name": package_name,
            "clone_url": clone_url,
            "committish": committish,
            "subdirectory": subdirectory,
            "spec": spec,
            "scm_type": scm_type,
            "srpm_build_method": srpm_build_method,
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else '' # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_scm(self, package_name, projectname, clone_url, committish='', subdirectory='', spec='',
                        scm_type='git', srpm_build_method='rpkg', ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_SCM)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "clone_url": clone_url,
            "committish": committish,
            "subdirectory": subdirectory,
            "spec": spec,
            "scm_type": scm_type,
            "srpm_build_method": srpm_build_method,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def edit_package_rubygems(self, package_name, projectname, gem_name, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_edit_url(ownername, projectname, package_name, SOURCE_TYPE_RUBYGEMS)
        data = {
            "package_name": package_name,
            "gem_name": gem_name,
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else '' # TODO: False/True gets converted to 'False'/'True' in FE, try to solve better

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_rubygems(self, package_name, projectname, gem_name, ownername=None, webhook_rebuild=None):
        request_url = self.get_package_add_url(ownername, projectname, SOURCE_TYPE_RUBYGEMS)
        response = self.process_package_action(request_url, ownername, projectname, data={
            "package_name": package_name,
            "gem_name": gem_name,
            "webhook_rebuild": 'y' if webhook_rebuild else '',
        })
        return response

    def edit_package_custom(self, package_name, projectname,
            script, script_chroot=None, script_builddeps=None,
            script_resultdir=None,
            ownername=None, webhook_rebuild=None):

        request_url = self.get_package_edit_url(ownername, projectname,
                package_name, SOURCE_TYPE_CUSTOM)

        data = {
            "package_name": package_name,
            "script": script,
            "builddeps": script_builddeps,
            "resultdir": script_resultdir,
            "chroot": script_chroot,
        }
        if webhook_rebuild != None:
            data['webhook_rebuild'] = 'y' if webhook_rebuild else ''

        response = self.process_package_action(request_url, ownername, projectname, data)
        return response

    def add_package_custom(self, package_name, projectname,
            script, script_chroot=None, script_builddeps=None,
            script_resultdir=None,
            ownername=None, webhook_rebuild=None):

        request_url = self.get_package_add_url(ownername, projectname,
                SOURCE_TYPE_CUSTOM)
        response = self.process_package_action(request_url, ownername,
                projectname, data={
                    "package_name": package_name,
                    "script": script,
                    "builddeps": script_builddeps,
                    "resultdir": script_resultdir,
                    "chroot": script_chroot,
                    "webhook_rebuild": 'y' if webhook_rebuild else '',
                },
        )
        return response

    def process_package_action(self, request_url, ownername, projectname, data, fetch_functor=None):
        if not ownername:
            ownername = self.username

        # @TODO refactor this hacky part
        # @TODO I want to have this function for various kind of actions, not only packages
        if fetch_functor:
            resp_data = fetch_functor(request_url, data, method="post")
        else:
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
            repos=None, initial_pkgs=None, disable_createrepo=None,
            unlisted_on_hp=False, enable_net=True, persistent=False,
            auto_prune=True, use_bootstrap_container=None,
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
            :param auto_prune: [optional] If backend auto-deletion script should be run for the project
            :param use_bootstrap_container: [optional] If mock bootstrap container is used to initialize the buildroot

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
            "auto_prune": "y" if auto_prune else "",
            "use_bootstrap_container": "y" if use_bootstrap_container else "",
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
                       repos=None, disable_createrepo=None, unlisted_on_hp=None,
                       enable_net=None, auto_prune=None,
                       use_bootstrap_container=None, chroots=None):
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
            :param auto_prune: [optional] If backend auto-deletion script should be run for the project
            :param use_bootstrap_container: [optional] If mock bootstrap container is used to initialize the buildroot
            :param chroots: [optional] list of chroots that should be enabled in the project. When not ``None``,
                selected chroots will be enabled while current chroots
                will not remain enabled if they are not specified.

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
        if auto_prune != None:
            data["auto_prune"] = "y" if auto_prune else ""
        if use_bootstrap_container != None:
            data["use_bootstrap_container"] = "y" if use_bootstrap_container else ""
        if chroots != None:
            data["chroots"] = " ".join(chroots)

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

    def edit_chroot(self, projectname, chrootname, ownername=None,
                      upload_comps=None, delete_comps=None, packages=None, repos=None):
        """ Edits chroot settings.
            Auth required.

            :param projectname: Copr project name
            :param chrootname: chroot name
            :param ownername: [optional] owner of the project
            :param upload_comps: file path to the comps.xml file
            :param delete_comps: True if comps.xml should be removed
            :param packages: buildroot packages for the chroot
            :param repos: buildroot additional repos

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.ProjectHandle`
                - text fields: "buildroot_pkgs"
        """

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/chroot/edit/{3}/".format(
            self.api_url, ownername, projectname, chrootname
        )
        multipart = False
        headers = None
        data = {}
        if upload_comps:
            try:
                f = open(upload_comps, "rb")
                data["upload_comps"] = (os.path.basename(f.name), f, "application/text")
                multipart = True
            except IOError as e:
                raise CoprRequestException(e)
        if delete_comps != None:
            data["delete_comps"] = "y" if delete_comps else ""
        if packages != None:
            data["buildroot_pkgs"] = packages
        if repos != None:
            data["repos"] = repos

        if multipart:
            data = MultipartEncoder(data)
            headers={'Content-Type': data.content_type}

        result_data = self._fetch(url, data, method="post", headers=headers)

        response = CoprResponse(
            client=self,
            method="post",
            data=result_data,
            request_kwargs={
                "projectname": projectname,
                "ownername": ownername
            },
            parsers=[
                CommonMsgErrorOutParser,
                CoprChrootParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname,
            username=ownername
        )
        return response

    def get_chroot(self, projectname, ownername, chrootname=None):
        """Returns copr_chroot data"""

        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/chroot/get/{3}/".format(
            self.api_url, ownername, projectname, chrootname
        )
        resp_data = self._fetch(url)

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
                CoprChrootParser,
            ]
        )
        response.handle = BaseHandle(
            self, response=response,
            projectname=projectname,
            username=ownername
        )

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
        """ @deprecated to edit_chroot
            Modifies chroot used in project

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

    def get_build_config(self, project, chroot):
        """
        Return build configuration for given project/chroot.
        :param project: project name, e.g. USER/PROJ, or @GROUP/PROJ.
        :param chroot: chroot name, e.g. fedora-rawhide-x86_64
        :return: :py:class:`~.responses.CoprResponse`
            with additional fields:
            - **build_config**: generated build config contents (dict)
        """
        url = "{0}/coprs/{1}/build-config/{2}".format(
            self.api_url,
            project,
            chroot,
        )
        data = self._fetch(url, skip_auth=True)
        response = CoprResponse(
            client=self,
            method="get_build_config",
            data=data,
            parsers=[
                CommonMsgErrorOutParser,
                BuildConfigParser,
            ]
        )
        return response

    def get_module_repo(self, owner, copr, name, stream, version, arch):
        """ Gets URL to module DNF repository

            :param owner: str owner name (can be user or @group)
            :param copr: str copr name
            :param name: str module name
            :param stream: str module stream
            :param version: int module version
            :param arch: str build architecture

            :return: :py:class:`~.responses.CoprResponse`
                with additional fields:

                - **handle:** :py:class:`~.responses.BaseHandle`
                - text fields: "repo"

        """
        url = "{}/module/repo/".format(self.api_url)
        data = {"owner": owner, "copr": copr, "name": name, "stream": stream, "version": version, "arch": arch}

        fetch = self._fetch(url, data=data, skip_auth=True, method="post")
        response = CoprResponse(
            client=self,
            method="get_module_repo",
            data=fetch,
            parsers=[
                CommonMsgErrorOutParser,
                ProjectListParser
            ]
        )
        response.handle = BaseHandle(client=self, response=response)
        return response

    def build_module(self, modulemd, ownername=None, projectname=None):
        if not ownername:
            ownername = self.username

        url = "{0}/coprs/{1}/{2}/module/build/".format(
            self.api_url, ownername, projectname
        )

        if isinstance(modulemd, io.BufferedIOBase):
            data = {"modulemd": (os.path.basename(modulemd.name), modulemd, "application/x-rpm")}
        else:
            data = {"scmurl": modulemd, "branch": "master"}

        def fetch(url, data, method):
            m = MultipartEncoder(data)
            monit = MultipartEncoderMonitor(m, lambda x: x)
            return self._fetch(url, monit, method="post", headers={'Content-Type': monit.content_type})

        # @TODO Refactor process_package_action to be general purpose
        response = self.process_package_action(url, None, None, data=data, fetch_functor=fetch)
        return response
