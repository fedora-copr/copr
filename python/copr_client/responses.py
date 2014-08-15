import weakref


class BaseResponse(object):
    """
        Base class for API responses.
        Some response provides further actions based on response content.
    """
    _simple_fields = []

    def __init__(self, client, response):
        """
        :param client: copr_client.main.Client
        :param response:
        """
        self.response = response
        self.client = weakref.proxy(client)

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
        raise NotImplementedError()


class ProjectMixin(object):
    """
        Provides methods related to copr project.
        Object must have fields "client" and "project_name"
    """
    def get_project_details(self):
        return self.client.get_project_details(self.project_name)

    def delete_project(self):
        return self.client.delete_project(self.project_name)


class ProjectWrapper(object):
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
    _simple_fields = ["output", "repos"]

    def __init__(self, client, response, username=None):
        super(GetProjectsListResponse, self).__init__(client, response)
        self.username = username or self.client.username

    @property
    def projects(self):
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


class CreateProjectResponse(ProjectMixin, BaseResponse):
    _simple_fields = ["message", "output"]

    def __init__(self, client, response,
                 name, description, instructions,
                 chroots, repos, initial_pkgs):
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


class ModifyProjectResponse(ProjectMixin, BaseResponse):
    def __init__(self, client, response,
                 name, description=None,
                 instructions=None, repos=None):
        super(ModifyProjectResponse, self).__init__(client, response)
        self.project_name = name
        self.description = description
        self.instructions = instructions
        self.repos = repos


class ProjectDetailsResponse(ProjectMixin, BaseResponse):
    _simple_fields = ["detail", "output"]

    def __init__(self, client, response, name):
        super(ProjectDetailsResponse, self).__init__(client, response)
        self.project_name = name

    def __str__(self):
        if hasattr(self, "detail"):
            return str(self.detail)

    def __unicode__(self):
        if hasattr(self, "detail."):
            return unicode(self.detail)

    def repeat_action(self):
        return self.get_project_details()


class DeleteProjectResponse(ProjectMixin, BaseResponse):
    _simple_fields = ["message", "output"]

    def __init__(self, client, response, name):
        super(DeleteProjectResponse, self).__init__(client, response)
        self.project_name = name

    def __str__(self):
        if hasattr(self, "message"):
            return str(self.message)

    def __unicode__(self):
        if hasattr(self, "message"):
            return unicode(self.message)

    def repeat_action(self):
        return self.delete_project()


class BuildMixin(object):
    """
        Provides methods related to individual builds
        Object must have fields "client" and "build_id"
    """
    def get_build_status(self):
        return self.client.get_build_status(self.build_id)

    def get_build_details(self):
        return self.client.get_build_details(self.build_id)

    def cancel_build(self):
        return self.client.cancel_build(self.build_id)

    def __str__(self):
        if not self.response:
            return super(BuildMixin, self).__str__()
        elif self.response["output"] == "ok":
            return self.response["status"]
        else:
            return self.response["error"]


class BuildStatusResponse(BuildMixin, BaseResponse):
    _simple_fields = ["status", "output", "error"]

    def __init__(self, client, response, build_id):
        super(BuildStatusResponse, self).__init__(client, response)
        self.build_id = build_id

    def repeat_action(self):
        return self.get_build_status()


class BuildDetailsResponse(BuildMixin, BaseResponse):
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


class CancelBuildResponse(BuildMixin, BaseResponse):
    _simple_fields = ["message", "output", "error"]

    def __init__(self, client, response, build_id):
        super(CancelBuildResponse, self).__init__(client, response)
        self.build_id = build_id

    def repeat_action(self):
        return self.client.cancel_build(self.build_id)

    # def __str__(self):
    #     if not self.response:
    #         return super(CancelBuildResponse, self).__str__()
    #     elif self.response["output"] == "ok":
    #         return self.response["status"]
    #     else:
    #         return self.response["error"]


class BuildRequestResponse(ProjectMixin, BaseResponse):
    _simple_fields = ["message", "output", "error", "ids"]

    def __init__(self, client, response,
                 copr_project, pkgs, memory, timeout, chroots):
        super(BuildRequestResponse, self).__init__(client, response)
        self.copr_project = copr_project
        self.pkgs = pkgs
        self.memory = memory
        self.timeout = timeout
        self.chroots = chroots

    def repeat_action(self):
        return self.client.send_new_build(
            copr_project=self.copr_project,
            pkgs=self.pkgs,
            memory=self.memory,
            timeout=self.timeout,
            chroots=self.chroots
        )


class ProjectChrootMixin(ProjectMixin):
    """
        Provides methods related to project chroots
        Object must have fields "client", "project_name", "chroot"
    """
    def get_project_chroot_details(self):
        return self.client.get_project_chroot_details(self.project_name, self.chroot)

    def modify_project_chroot_details(self, pkgs):
        return self.client.modify_project_chroot_details(
            self.project_name, self.chroot, pkgs=pkgs)


class ProjectChrootDetailsResponse(ProjectChrootMixin, BaseResponse):
    def __init__(self, client, response, name, chroot):
        super(ProjectChrootDetailsResponse, self).__init__(client, response)
        self.project_name = name
        self.chroot = chroot

    def repeat_action(self):
        return self.get_project_details()


class ModifyProjectChrootResponse(ProjectChrootMixin, BaseResponse):
    def __init__(self, client, response, name, chroot, pkgs):
        super(ModifyProjectChrootResponse, self).__init__(client, response)
        self.project_name = name
        self.chroot = chroot
        self.pkgs = pkgs

    def repeat_action(self):
        return self.modify_project_chroot_details(self.pkgs)


class SearchResponse(BaseResponse):
    _simple_fields = ["output", "repos"]

    def __init__(self, client, response, query):
        super(SearchResponse, self).__init__(client, response)
        self.query = query

    def repeat_action(self):
        return self.client.search_projects(self.query)
