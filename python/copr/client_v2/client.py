# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from abc import ABCMeta, abstractproperty

import sys
import os
import logging
import weakref

import six
from six import with_metaclass
from six.moves import configparser

from .resources import Root
from .handlers import ProjectHandle, ProjectChrootHandle, BuildHandle, MockChrootHandle, BuildTaskHandle
from .net_client import NetClient

if sys.version_info < (2, 7):
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
else:
    from logging import NullHandler

from ..exceptions import CoprConfigException, CoprNoConfException
from ..util import UnicodeMixin

log = logging.getLogger(__name__)
log.addHandler(NullHandler())


class HandlersProvider(object, with_metaclass(ABCMeta)):

    @abstractproperty
    def projects(self):
        """
        :rtype: ProjectHandle
        """
        pass

    @abstractproperty
    def project_chroots(self):
        """
        :rtype: ProjectChrootHandle
        """
        pass

    @abstractproperty
    def builds(self):
        """
        :rtype: BuildHandle
        """
        pass

    @abstractproperty
    def build_tasks(self):
        """
        :rtype: BuildTaskHandle
        """
        pass

    @abstractproperty
    def mock_chroots(self):
        """
        :rtype: MockChrootHandle
        """
        pass


class CoprClient(UnicodeMixin, HandlersProvider):
    """ Main interface to the copr service

    :param NetClient net_client: wrapper for http requests
    :param unicode root_url: used as copr projects root
    :param bool no_config: helper flag to indicate that no config was provided

    Could be created:
        - using static method :meth:`~copr.client_v2.client.CoprClient.create_from_file_config`
        - using static method :meth:`~copr.client_v2.client.CoprClient.create_from_params`

    If you create Client directly call :meth:`CoprClient.post_init` method after the creation.
    """

    def __init__(self, net_client, root_url=None, no_config=False):
        """

        """
        self.nc = net_client
        self.root_url = root_url or u"https://copr.fedorainfracloud.org"

        self.no_config = no_config
        self._post_init_done = False

        self.root = None

        self._projects = None
        self._project_chroots = None
        self._builds = None
        self._build_tasks = None
        self._mock_chroots = None

    def _check_client_init(self):
        if not self._post_init_done:
            raise RuntimeError("CoprClient wasn't initialized, use class-methods "
                               "create_from* to get instance of CoprClient")

    @property
    def projects(self):
        """
        :rtype: :py:class:`~copr.client_v2.handlers.ProjectHandle`
        """
        self._check_client_init()
        return self._projects

    @property
    def project_chroots(self):
        """
        :rtype: :py:class:`~copr.client_v2.handlers.ProjectChrootHandle`
        """
        self._check_client_init()
        return self._project_chroots

    @property
    def builds(self):
        """
        :rtype: :py:class:`~copr.client_v2.handlers.BuildHandle`
        """
        self._check_client_init()
        return self._builds

    @property
    def build_tasks(self):
        """
        :rtype: :py:class:`~copr.client_v2.handlers.BuildTaskHandle`
        """
        self._check_client_init()
        return self._build_tasks

    @property
    def mock_chroots(self):
        """
        :rtype: :py:class:`~copr.client_v2.handlers.MockChrootHandle`
        """
        self._check_client_init()
        return self._mock_chroots

    def __unicode__(self):
        return (
            u"<Copr client. api root url: {}, config provided: {}, net client: {}>"
            .format(self.root_url, not self.no_config, self.nc)
        )

    @property
    def api_root(self):
        """
            Url to API endpoint
        """
        return "{0}/api_2".format(self.root_url)

    @classmethod
    def create_from_params(cls, root_url=None, login=None, token=None):
        """ Create client instance using the given parameters

        :param str root_url: Url to the Copr service, default: "http://copr.fedoraproject.org"
        :param str login: api login
        :param str token: api token

        :rtype: :py:class:`.client_v2.client.CoprClient`
        """
        nc = NetClient(login, token)
        client = cls(nc, root_url, no_config=True)
        client.post_init()
        return client

    @classmethod
    def create_from_file_config(cls, filepath=None, ignore_error=False):
        """
        Creates Copr client using the information from the config file.

        :param filepath: specifies config location,
            default: "~/.config/copr"
        :type filepath: `str`
        :param bool ignore_error: When true and config is missing,
            creates default Client without credentionals

        :rtype: :py:class:`.client_v2.client.CoprClient`
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
                return cls.create_from_params()
        else:
            try:
                for field in ["login", "token", "copr_url"]:
                    if six.PY3:
                        config[field] = raw_config["copr-cli"].get(field, None)
                    else:
                        config[field] = raw_config.get("copr-cli", field, None)
                nc = NetClient(config["login"], config["token"])
                client = cls(nc, root_url=config["copr_url"], )

            except configparser.Error as err:
                if not ignore_error:
                    raise CoprConfigException(
                        "Bad configuration file: {0}".format(err))
                else:
                    return cls.create_from_params()

        client.post_init()
        return client

    def post_init(self):
        """ Finalizes client initialization by querying API root info
        """

        log.debug("Getting root resources")

        response = self.nc.request(self.api_root)

        # obtain api info info
        self.root = Root.from_response(response, self.root_url)

        # instantiating handlers
        self._projects = ProjectHandle(
            weakref.proxy(self), self.nc, root_url=self.root_url,
            projects_href=self.root.get_href_by_name(u"projects"),)
        self._project_chroots = ProjectChrootHandle(
            weakref.proxy(self), self.nc, root_url=self.root_url)

        self._builds = BuildHandle(
            weakref.proxy(self), self.nc, root_url=self.root_url,
            builds_href=self.root.get_href_by_name(u"builds"),)

        self._build_tasks = BuildTaskHandle(
            weakref.proxy(self), self.nc, root_url=self.root_url,
            build_tasks_href=self.root.get_href_by_name("build_tasks")
        )

        self._mock_chroots = MockChrootHandle(
            weakref.proxy(self), self.nc, root_url=self.root_url,
            href=self.root.get_href_by_name(u"mock_chroots")
        )

        self._post_init_done = True
