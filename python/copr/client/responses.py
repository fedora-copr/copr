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


class BaseResponse(object):
    """
        Base class for API responses.
    """
    _simple_fields = []

    def __init__(self, client, response, username=None):
        """
        @param client: L{CoprClient} which was used for request
        @param response: received response
        @type response: C{dict}

        @param username: alternative username if needed
        """
        self.response = response
        self.client = weakref.proxy(client)
        self.username = username

    def __str__(self):
        return str(self.response)

    def __unicode__(self):
        return unicode(self.response)

    def __getattr__(self, item):
        if item not in self._simple_fields:
            raise KeyError(item)
        if self.response is None:
            raise RuntimeError()

        return self.response[item]

    def repeat_action(self):
        """ Repeats action which produced by `this` response object
        """
        raise NotImplementedError()


class GenericProjectResponse(BaseResponse):
    """
        Provides methods related to copr project.
        Object must have fields "client" and "project_name"
    """
    def get_project_details(self):
        """ Shortcut to L{CoprClient.get_project_details}

            @rtype: L{ProjectDetailsResponse}
        """
        return self.client.get_project_details(
            self.project_name, username=self.username)

    def delete_project(self):
        """ Shortcut to L{CoprClient.delete_project}

            @rtype: L{ProjectDetailsResponse}
        """

        return self.client.delete_project(
            self.project_name, username=self.username)

    def modify_project(self, **kwargs):
        """
            Shortcut to L{CoprClient.modify_project}

            For parameters see L{CoprClient.modify_project}

            @rtype: L{ModifyProjectResponse}
        """
        kwargs_to_apply = {
            "projectname": self.project_name,
            "username": self.username
        }
        kwargs_to_apply.update(kwargs)
        return self.client.modify_project(**kwargs_to_apply)


class ProjectWrapper(object):
    """
        Helper class to represent project objects
    """
    def __init__(self, username, projectname,
                 description=None, instructions=None,
                 yum_repos=None, additional_repos=None):

        self.username = username
        self.projectname = projectname
        self.description = description
        self.instructions = instructions
        self.yum_repos = yum_repos or {}
        self.additional_repos = additional_repos or {}

    def __str__(self):
        out = list()
        out.append("Name: {0}".format(self.projectname))
        out.append("  Description: {0}".format(self.description))

        if self.yum_repos:
            out.append("  Yum repo(s):")
            for k in sorted(self.yum_repos.keys()):
                out.append("    {0}: {1}".format(k, self.yum_repos[k]))
        if self.additional_repos:
            out.append("  Additional repo: {0}".format(self.additional_repos))
        if self.instructions:
            out.append("  Instructions: {0}".format(self.instructions))

        out.append("")
        return "\n".join(out)


class GetProjectsListResponse(BaseResponse):
    """
        Wrapper for response to`project list`.
    """
    _simple_fields = ["output", "repos"]

    def __init__(self, client, response, username=None):
        super(GetProjectsListResponse, self).__init__(
            client, response, username)

    @property
    def projects(self):
        """
            Provides list of L{ProjectWrapper} objects
        """
        if not self.response or \
                self.response.get("output", None) != "ok" or \
                not self.response.get("repos"):
            return None
        else:
            return [
                ProjectWrapper(
                    username=self.username,
                    projectname=prj.get("name"),
                    description=prj.get("description"),
                    yum_repos=prj.get("yum_repos"),
                    additional_repos=prj.get("additional_repos"),
                ) for prj in self.response["repos"]
            ]


class CreateProjectResponse(GenericProjectResponse):
    """
        Wrapper for response to `create project`.
    """
    _simple_fields = ["message", "output"]

    def __init__(self, client, response,
                 name, description, instructions,
                 chroots, repos, initial_pkgs):
        """
            @type client: L{CoprClient}
        """

        super(CreateProjectResponse, self).__init__(client, response)
        self.project_name = name
        self.description = description
        self.instructions = instructions
        self.chroots = chroots
        self.repos = repos
        self.initial_pkgs = initial_pkgs

    def __str__(self):
        if hasattr(self, "message"):
            return str(self.message)

    def __unicode__(self):
        if hasattr(self, "message"):
            return unicode(self.message)


class ModifyProjectResponse(GenericProjectResponse):
    """
        Wrapper for response to `modify project`.
    """
    def __init__(self, client, response,
                 projectname, username=None,
                 description=None, instructions=None, repos=None):
        super(ModifyProjectResponse, self).__init__(client, response, username)
        self.project_name = projectname
        self.description = description
        self.instructions = instructions
        self.repos = repos

    def repeat_action(self):
        """
           @rtype: L{ModifyProjectResponse}
        """
        kwargs = {}
        if self.description:
            kwargs["description"] = self.description
        if self.instructions:
            kwargs["instructions"] = self.instructions
        if self.repos:
            kwargs["repos"] = self.repos

        return self.modify_project(**kwargs)


class ProjectDetailsResponse(GenericProjectResponse):
    """
        Wrapper for response to `project details`.
    """
    _simple_fields = ["detail", "output"]

    def __init__(self, client, response, name, username):
        super(ProjectDetailsResponse, self).__init__(client, response, username)
        self.project_name = name

    def __str__(self):
        if hasattr(self, "detail"):
            return str(self.detail)

    def __unicode__(self):
        if hasattr(self, "detail."):
            return unicode(self.detail)

    def repeat_action(self):
        """
            @rtype: L{ProjectDetailsResponse}
        """
        return self.get_project_details()


class DeleteProjectResponse(GenericProjectResponse):
    """
        Wrapper for response to `delete project`.
    """
    _simple_fields = ["message", "output"]

    def __init__(self, client, response, projectname, username=None):
        super(DeleteProjectResponse, self).__init__(client, response, username)
        self.project_name = projectname

    def __str__(self):
        if hasattr(self, "message"):
            return str(self.message)

    def __unicode__(self):
        if hasattr(self, "message"):
            return unicode(self.message)

    def repeat_action(self):
        """
            @rtype: L{DeleteProjectResponse}
        """
        return self.delete_project()


class GenericBuildResponse(BaseResponse):
    """
        Provides methods related to individual builds
        Object must have fields "client" and "build_id"
    """
    def get_build_details(self):
        """
            Shortcut to L{CoprClient.get_build_details}

            @rtype: L{BuildDetailsResponse}
        """
        return self.client.get_build_details(self.build_id)

    def cancel_build(self):
        """
            Shortcut to L{CoprClient.cancel_build}

            @rtype: L{CancelBuildResponse}
        """
        return self.client.cancel_build(self.build_id)

    def __str__(self):
        if not self.response:
            return super(GenericBuildResponse, self).__str__()
        elif self.response["output"] == "ok":
            return self.response["status"]
        else:
            return self.response["error"]


class BuildDetailsResponse(GenericBuildResponse):
    """
        Wrapper for response to `get build details`.
    """
    _simple_fields = [
        'status', 'error', 'submitted_by', 'results', 'src_pkg', 'started_on',
        'submitted_on', 'owner', 'chroots', 'project', 'built_pkgs',
        'ended_on', 'output', 'src_version'
    ]

    def __init__(self, client, response, build_id):
        super(BuildDetailsResponse, self).__init__(client, response)
        self.build_id = build_id

    def repeat_action(self):
        return self.get_build_details()


class CancelBuildResponse(GenericBuildResponse):
    """
        Wrapper for response to `cancel build`.
    """
    _simple_fields = ["message", "output", "error"]

    def __init__(self, client, response, build_id):
        super(CancelBuildResponse, self).__init__(client, response)
        self.build_id = build_id

    def repeat_action(self):
        return self.client.cancel_build(self.build_id)


class BuildRequestResponse(GenericProjectResponse):
    """
        Wrapper for response to `send new build`.
    """
    _simple_fields = ["message", "output", "error", "ids"]

    def __init__(self, client, response,
                 copr_project, pkgs, memory, timeout, chroots, username=None):
        super(BuildRequestResponse, self).__init__(client, response, username)
        self.copr_project = copr_project
        self.pkgs = pkgs
        self.memory = memory
        self.timeout = timeout
        self.chroots = chroots

    def repeat_action(self):
        """
            @rtype: L{BuildRequestResponse}
        """
        return self.client.send_new_build(
            copr_project=self.copr_project,
            pkgs=self.pkgs,
            memory=self.memory,
            timeout=self.timeout,
            chroots=self.chroots
        )


class GenericChrootResponse(GenericProjectResponse):
    """
        Provides methods related to project chroots
        Object must have fields "client", "project_name", "chroot"
    """
    def get_project_chroot_details(self):
        """
            Shortcut to L{CoprClient.get_project_chroot_details}

            @rtype: L{ProjectChrootDetailsResponse}
        """
        return self.client.get_project_chroot_details(
            self.project_name, self.chroot)

    def modify_project_chroot_details(self, pkgs):
        """
            Shortcut to L{CoprClient.get_project_chroot_details}

            @rtype: L{ModifyProjectChrootResponse}
        """
        return self.client.modify_project_chroot_details(
            self.project_name, self.chroot, pkgs=pkgs)


class ProjectChrootDetailsResponse(GenericChrootResponse):
    """
        Wrapper for response to `get chroot details`.
    """
    def __init__(self, client, response, name, chroot, username=None):
        super(ProjectChrootDetailsResponse, self).__init__(
            client, response, username)
        self.project_name = name
        self.chroot = chroot

    def repeat_action(self):
        return self.get_project_chroot_details()


class ModifyProjectChrootResponse(GenericChrootResponse):
    """
        Wrapper for response to `modify chroot`.
    """
    def __init__(self, client, response, name, chroot, pkgs, username=None):
        super(ModifyProjectChrootResponse, self).__init__(
            client, response, username)
        self.project_name = name
        self.chroot = chroot
        self.pkgs = pkgs

    def repeat_action(self):
        return self.modify_project_chroot_details(self.pkgs)


class SearchResponse(BaseResponse):
    """
        Wrapper for response to `search project`.
    """
    _simple_fields = ["output", "repos"]

    def __init__(self, client, response, query):
        super(SearchResponse, self).__init__(client, response)
        self.query = query

    def repeat_action(self):
        """
            @rtype: L{SearchResponse}
        """

        return self.client.search_projects(self.query)
