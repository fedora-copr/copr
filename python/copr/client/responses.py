# pylint: disable=R0903
"""
Wrappers for Copr api response.
Response classes provide convenient representation of received data
and offer actions based on response content.
"""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import weakref

#
# TODO:  Add Response for collections?
# TODO:  what about copr_project-> chroot_list, build_list, repos_list
#
from ..util import UnicodeMixin


class CoprResponse(UnicodeMixin):
    """
        Wrapper for Copr api responses

        :ivar handle: handle object which provide shortcuts
            based on request and/or response data
            (:py:class:`~.responses.BaseHandle` and its derivatives)
        :ivar dict data: json structure from Copr api
    """

    def __init__(self, client, method, data,
                 request_kwargs=None, parsers=None):
        """
            :param method: what method was used to query api
            :param data: json structure returned from Copr

            :param parsers: list of parser to process response data
            :type parsers: list of client.parsers.IParser
        """
        self.method = method
        self.data = data
        self.request_kwargs = request_kwargs
        self.parsers = parsers or []
        self.client = client
        self._parsed_data = {}
        self.handle = None

    def __getattr__(self, item):
        if self.data is None:
            raise RuntimeError("No response data to access sub-item")

        if item in self._parsed_data:
            return self._parsed_data[item]
        else:
            for parser in self.parsers:
                if item in parser.provided_fields:
                    value = parser.parse(self.data, item,
                                         client=self.client,
                                         request_kwargs=self.request_kwargs)
                    self._parsed_data[item] = value
                    return value
            raise KeyError(str(item))

    def __unicode__(self):
        return str(self.data)


class BaseHandle(object):
    """
    Handles provide convenient shortcut methods. Useful methods
    provided by derived classes.

    Example::

        response = client.create_project("copr")
        response.handle # <-- ProjectHandle object
        print(response.handle.get_project_details().data)

    """

    def __init__(self, client, username=None, response=None, **kwargs):
        """
            :param client: client instance used for request
            :type client: CoprClient
        """
        self.client = client
        self.username = username

        if response:
            self.response = weakref.proxy(response)
        else:
            self.response = None


class ProjectHandle(BaseHandle):
    """
        Handle to deal with a single Copr project
    """

    def __init__(self, client, projectname, *args, **kwargs):
        """
            :param client: client instance used for request
            :type client: CoprClient

            :param projectname: Copr project name
        """
        super(ProjectHandle, self).__init__(client, *args, **kwargs)
        self.projectname = projectname

    def get_project_details(self):
        """
            Shortcut to :meth:`~.client.CoprClient.get_project_details`
        """
        return self.client.get_project_details(
            self.projectname, username=self.username)

    def modify_project(self, **kwargs):
        """
            Shortcut to :meth:`~.client.CoprClient.modify_project`
        """
        return self.client.modify_project(
            self.projectname, username=self.username, **kwargs
        )

    def delete_project(self):
        """
            Shortcut to :meth:`~.client.CoprClient.delete_project`
        """
        return self.client.delete_project(
            self.projectname, username=self.username)

    def create_new_build(self, src_pkgs, chroots=None):
        """
            Shortcut to :meth"`~.client.CoprClient.create_new_build'
        """
        return self.client.create_new_build(self.projectname,
                                            src_pkgs, chroots)


class BuildHandle(BaseHandle):
    """
        Handle to deal with a single build
    """

    def __init__(self, client, build_id, *args, **kwargs):
        """
            :param client: client instance used for request
            :type client: CoprClient
        """
        super(BuildHandle, self).__init__(client, *args, **kwargs)
        self.build_id = build_id

        self.projectname = kwargs.get("projectname", None)

    @property
    def project_handle(self):
        """
            Shortcut for :py:class:`.responses.ProjectHandle`
        """
        if not self.projectname:
            raise Exception("Project name for build {0} is unknown".
                            format(self.build_id))
        if not self.username:
            raise Exception("Project owner for build {0} is unknown".
                            format(self.build_id))

        return ProjectHandle(client=self.client,
                             username=self.username,
                             projectname=self.projectname)

    def get_build_details(self):
        """
            Shortcut to :meth:`~.client.CoprClient.get_build_details`
        """
        return self.client.get_build_details(self.build_id,
                                             username=self.username,
                                             projectname=self.projectname)

    def cancel_build(self):
        """
            Shortcut to :meth:`~.client.CoprClient.cancel_build`
        """
        return self.client.cancel_build(self.build_id,
                                        username=self.username,
                                        projectname=self.projectname)


class ProjectChrootHandle(BaseHandle):
    """
        Handle to deal with a single project chroot
    """
    def __init__(self, client, chrootname, *args, **kwargs):
        super(ProjectChrootHandle, self).__init__(client, *args, **kwargs)

        self.chrootname = chrootname
        self.projectname = kwargs.get("projectname", None)

    @property
    def project_handle(self):
        if not self.projectname:
            raise Exception("Project name  is unknown")
        if not self.username:
            raise Exception("Project owner for build {0} is unknown")

        return ProjectHandle(client=self.client,
                             username=self.username,
                             projectname=self.projectname)

    def get_project_chroot_details(self):
        """
        Shortcut to :meth:`~.client.CoprClient.get_project_chroot_details`
        """
        return self.client.get_project_chroot_details(
            chrootname=self.chrootname,
            projectname=self.projectname,
            username=self.username)

    def modify_project_chroot_details(self, pkgs=None):
        """
        Shortcut to :meth:`~.client.CoprClient.modify_project_chroot_details`
        """
        return self.client.modify_project_chroot_details(
            self.projectname, self.chrootname, pkgs=pkgs)


class PackageHandle(BaseHandle):
    def __init__(self, client, ownername, projectname, name, *args, **kwargs):
        super(PackageHandle, self).__init__(client, *args, **kwargs)

        self.ownername = ownername
        self.projectname = projectname
        self.name = name


############################################################

class ProjectWrapper(UnicodeMixin):
    """
        Helper class to represent project objects

        ``__str__`` overridden to produces pretty formatted representation

        :ivar handle: :py:class:`.responses.ProjectHandle`

        :ivar username: project owner
        :ivar projectname: project names
    """

    def __init__(self, client, username, projectname,
                 description=None, instructions=None,
                 yum_repos=None, additional_repos=None):
        self.username = username
        self.projectname = projectname
        self.description = description
        self.instructions = instructions
        self.yum_repos = yum_repos or {}
        self.additional_repos = additional_repos or {}

        self.handle = ProjectHandle(client=client, projectname=projectname,
                                    username=username, response=None)

    def __unicode__(self):
        out = list()
        out.append(u"Name: {0}".format(self.projectname))
        out.append(u"  Description: {0}".format(self.description))

        if self.yum_repos:
            out.append(u"  Yum repo(s):")
            for k in sorted(self.yum_repos.keys()):
                out.append(u"    {0}: {1}".format(k, self.yum_repos[k]))
        if self.additional_repos:
            out.append(u"  Additional repo: {0}".format(self.additional_repos))
        if self.instructions:
            out.append(u"  Instructions: {0}".format(self.instructions))

        out.append(u"")
        return u"\n".join(out)


class BuildWrapper(object):
    """
        Helper class to represent build objects

        :ivar handle: :py:class:`.responses.BuildHandle`

        :ivar username: project owner
        :ivar projectname: project names
        :ivar int build_id: build identifier
    """

    def __init__(self, client, username, projectname, build_id,
                 status=None):
        self.username = username
        self.projectname = projectname
        self.build_id = build_id

        self.status = status

        self.handle = BuildHandle(client=client, build_id=build_id,
                                  projectname=projectname,
                                  username=username, response=None)


class ProjectChrootWrapper(object):
    """
        Helper class to represent project chroot objects

        :ivar handle: :py:class:`.responses.ProjectChrootHandle`

        :ivar username: project owner
        :ivar projectname: project names
        :ivar chrootname: chroot name
    """

    def __init__(self, client, username, projectname, chrootname,
                 repo_url=None):
        self.username = username
        self.projectname = projectname
        self.chrootname = chrootname

        self.repo_url = repo_url

        self.handle = ProjectChrootHandle(
            client=client, chrootname=chrootname,
            projectname=projectname,
            username=username, response=None
        )


class PackageWrapper(UnicodeMixin):
    def __init__(self, client, ownername, projectname, **data):
        self.client = client
        self.ownername = ownername
        self.projectname = projectname
        self.data = data
        self.handle = PackageHandle(
            client=self.client,
            ownername=self.ownername, projectname=self.projectname,
            copr_id=self.copr_id, enable_net=self.enable_net, name=self.name,
            id=self.id, source_json=self.source_json,
            source_type=self.source_type, webhook_rebuild=self.webhook_rebuild
        )

    def __getattr__(self, item):
        try:
            return self.data[item]
        except KeyError as e:
            raise AttributeError()

    def for_json(self):
        return self.data


class CoprChrootWrapper(UnicodeMixin):
    def __init__(self, client, ownername, projectname, **data):
        self.client = client
        self.ownername = ownername
        self.projectname = projectname
        self.data = data
        self.handle = None

    def __getattr__(self, item):
        try:
            return self.data[item]
        except KeyError as e:
            raise AttributeError()

    def for_json(self):
        return self.data
