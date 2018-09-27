# coding: utf-8
from abc import abstractmethod, ABCMeta
import json
import os

from copr.client_v2.net_client import RequestError, MultiPartTuple
from .entities import ProjectChrootEntity, ProjectCreateEntity
from .resources import Project, OperationResult, ProjectList, ProjectChroot, ProjectChrootList, Build, BuildList, \
    MockChroot, MockChrootList, BuildTask, BuildTaskList


class AbstractHandle(object):
    """
    :param client: Should be used only to access other handlers
    :type client: copr.client_v2.client.HandlersProvider
    :type nc: copr.client_v2.net_client.NetClient
    """
    __metaclass__ = ABCMeta

    def __init__(self, client, nc, root_url):
        self.client = client
        self.nc = nc
        self.root_url = root_url

    @abstractmethod
    def get_base_url(self, *args, **kwargs):
        pass


class BuildHandle(AbstractHandle):
    def __init__(self, client, nc, root_url, builds_href):
        super(BuildHandle, self).__init__(client, nc, root_url)
        self.builds_href = builds_href
        self._base_url = "{0}{1}".format(self.root_url, builds_href)

    def get_base_url(self):
        return self._base_url

    def get_one(self, build_id):
        """ Retrieves builds object

        :param int build_id: id of the target build
        :rtype: :py:class:`~.resources.Build`
        """

        options = {"build_id": build_id}
        url = "{0}/{1}".format(self.get_base_url(), build_id)
        response = self.nc.request(url)
        return Build.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            options=options,
        )

    def get_list(self, project_id=None, owner=None, limit=None, offset=None):
        """ Retrieves builds object according to the given parameters

        :param owner: name of the project owner
        :param project_id: id of the project
        :param limit: limit number of builds
        :param offset: number of builds to skip

        :rtype: :py:class:`~.resources.BuildList`
        """
        options = {
            "project_id": project_id,
            "owner": owner,
            "limit": limit,
            "offset": offset
        }

        response = self.nc.request(self.get_base_url(), query_params=options)
        return BuildList.from_response(self, response, options)

    def cancel(self, build_entity):
        """ Cancels the given build

        :param build_entity: build entity to delete
        :type build_entity: :py:class:`~.copr.client_v2.entities.BuildEntity`

        :rtype: :py:class:`.OperationResult`
        """
        build_id = build_entity.id
        build_entity.state = "canceled"

        url = "{0}/{1}".format(self.get_base_url(), build_id)
        response = self.nc.request(url, data=build_entity.to_json(), method="PUT", do_auth=True)
        return OperationResult(self, response)

    def delete(self, build_id):
        """ Deletes the given build

        :param int build_id: build id to delete

        :rtype: :py:class:`.OperationResult`
        """

        url = "{0}/{1}".format(self.get_base_url(), build_id)
        response = self.nc.request(url, method="delete", do_auth=True)
        return OperationResult(self, response, expected_status=204)

    def _process_create_response(self, request_data, response):
        op_result = OperationResult(self, response, expected_status=201)
        if op_result.is_successful():
            build_response = self.nc.get(op_result.new_location)
            return Build.from_response(
                handle=self, response=build_response,
                data_dict=build_response.json
            )
        else:
            raise RequestError(
                "Got unexpected status code at create build request",
                url=self.get_base_url(),
                request_body=request_data, response=response
            )

    def create_from_url(self, project_id, srpm_url,
                        chroots=None, enable_net=True):

        """
        Creates new build using public url to the srpm file

        :param int project_id: id of the project where we want to submit new build
        :param str srpm_url: url to the source rpm
        :param list chroots: which chroots should be used during the build
        :param bool enable_net: allows to disable network access during the build, default: True

        :return: created build
        :rtype: :py:class:`~.resources.Build`
        """

        chroots = list(map(str, chroots or list()))
        content = {
            "project_id": int(project_id),
            "srpm_url": str(srpm_url),
            "chroots": chroots,
            "enable_net": bool(enable_net)
        }
        data = json.dumps(content)
        response = self.nc.request(
            self.get_base_url(),
            data=data, method="POST", do_auth=True,
        )

        return self._process_create_response(data, response)

    def create_from_file(self, project_id, file_path=None,
                         file_obj=None, file_name=None,
                         chroots=None, enable_net=True):
        """
        Creates new build using srpm upload, please specify
        either ``file_path`` or (``file_obj``, ``file_name``    ).

        :param int project_id: id of the project where we want to submit new build

        :param str file_path: path to the srpm file

        :param file file_obj: file-like object to read from
        :param str file_name: name for the uploaded file

        :param list chroots: which chroots should be used during the build
        :param bool enable_net: allows to disable network access during the build, default: True

        :return: created build
        :rtype: :py:class:`~.resources.Build`
        """

        chroots = list(map(str, chroots or list()))
        content = {
            "project_id": int(project_id),
            "chroots": chroots,
            "enable_net": bool(enable_net)
        }

        metadata = MultiPartTuple(
            "metadata", name=None,
            obj=json.dumps(content), content_type="application/json")

        if file_path is not None:
            with open(file_path, "rb") as f_obj:
                f_name = os.path.basename(f_obj.name)
                parts, response = self._do_upload_request(f_name, f_obj, metadata)
        elif file_obj is not None and file_name is not None:
            parts, response = self._do_upload_request(file_name, file_obj, metadata)
        else:
            raise RuntimeError("Please provide file_path or file_obj and file_name")

        return self._process_create_response(parts, response)

    def _do_upload_request(self, f_name, f_obj, metadata):
        srpm = MultiPartTuple("srpm", name=f_name, obj=f_obj,
                              content_type="appliction/x-rpm")
        parts = [metadata, srpm]
        response = self.nc.request_multipart(
            url=self.get_base_url(),
            method="POST",
            data_parts=parts,
            do_auth=True,
        )
        return parts, response

    def get_build_tasks_handle(self):
        """
        :rtype: BuildTasksHandle
        """
        return self.client.build_tasks

class BuildTaskHandle(AbstractHandle):

    def __init__(self, client, nc, root_url, build_tasks_href):
        super(BuildTaskHandle, self).__init__(client, nc, root_url)
        self.build_tasks_href = build_tasks_href
        self._base_url = "{0}{1}".format(self.root_url, build_tasks_href)

    def get_base_url(self):
        return self._base_url

    def get_list(self, owner=None, project_id=None, build_id=None,
                 state=None, offset=None, limit=None):

        """ Retrieves build tasks list according to the given parameters

        :param str owner: build tasks from the project owner by this user
        :param int project_id: get tasks only from this project,
            when used query parameter ``owner`` is ignored
        :param int build_id: get tasks only from this build,
            when used query parameters ``owner`` and ``project_id`` are ignored
        :param str state: get build tasks only with this state, allowed values:
            ``failed``, ``succeeded``, ``canceled``, ``running``,
            ``pending``, ``starting``, ``importing``
        :param int limit: limit number of projects
        :param int offset: number of projects to skip

        :rtype: :py:class:`~.resources.BuildTaskList`
        """
        options = {
            "owner": owner,
            "project_id": project_id,
            "build_id": build_id,
            "state": state,
            "limit": limit,
            "offset": offset
        }

        response = self.nc.request(self.get_base_url(), query_params=options)
        return BuildTaskList.from_response(self, response, options)

    def get_one(self, build_id, chroot_name):
        """ Retrieves single build task object


        :param int build_id: id of the build
        :param str chroot_name: name of the build chroot
        :rtype:  :py:class:`~.resources.BuildTask`
        """

        url = "{0}/{1}/{2}".format(self.get_base_url(), build_id, chroot_name)
        response = self.nc.request(url)
        return BuildTask.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
        )


class ProjectHandle(AbstractHandle):

    def __init__(self, client, nc, root_url, projects_href):
        super(ProjectHandle, self).__init__(client, nc, root_url)
        self.projects_href = projects_href
        self._base_url = "{0}{1}".format(self.root_url, projects_href)

    def get_base_url(self):
        return self._base_url

    def get_list(self, search_query=None, owner=None, name=None, limit=None, offset=None):
        """ Retrieves projects object according to the given parameters

        :param str search_query: search projects with such string
        :param str owner: owner username
        :param str name: project name
        :param int limit: limit number of projects
        :param int offset: number of projects to skip

        :rtype: :py:class:`~.resources.ProjectList`
        """
        options = {
            "search_query": search_query,
            "owner": owner2user(owner),
            "group": owner2group(owner),
            "name": name,
            "limit": limit,
            "offset": offset
        }

        response = self.nc.request(self.get_base_url(), query_params=options)
        return ProjectList.from_response(self, response, options)

    def get_one(self, project_id):
        # todo: implement: , show_builds=False, show_chroots=False):
        """ Retrieves project object.

        :param int project_id: project identifier
        :rtype: :py:class:`~.resources.Project`
        """
        query_params = {
            # "show_builds": show_builds,
            # "show_chroots": show_chroots
        }

        url = "{0}/{1}".format(self.get_base_url(), project_id)
        response = self.nc.request(url, query_params=query_params)
        return Project.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            options=query_params
        )

    def create(
            self, name, owner, chroots, description=None, instructions=None,
            homepage=None, contact=None, disable_createrepo=None, build_enable_net=None,
            repos=None,
    ):
        """ Creates new project

        :param name: project name
        :param owner: username
        :param chroots: list of mock chroot to be used in project
        :param description:
        :param instructions:
        :param homepage:
        :param contact:
        :param bool disable_createrepo:
        :param bool build_enable_net:
        :param repos: list of additional repos enabled for builds

        :rtype: :py:class:`~.resources.Project`
        """

        new_entity = ProjectCreateEntity(
            owner=owner,
            group=owner2group(owner),
            name=name,
            chroots=chroots,
            description=description,
            instructions=instructions,
            homepage=homepage,
            contact=contact,
            disable_createrepo=disable_createrepo,
            build_enable_net=build_enable_net,
            repos=repos
        )

        url = self.get_base_url()
        request_data = new_entity.to_json()
        response = self.nc.request(url, method="post", data=request_data, do_auth=True)
        op_result = OperationResult(self, response, expected_status=201)
        if op_result.is_successful():
            response = self.nc.get(op_result.new_location)
            return Project.from_response(
                handle=self, response=response, data_dict=response.json)
        else:
            raise RequestError(
                "Got unexpected status code at create build request",
                url=self.get_base_url(),
                request_body=request_data, response=response
            )

    def update(self, project_entity):
        """ Updates project.

        :param project_entity: project entity to use for update
        :type project_entity: :py:class:`~.ProjectEntity`
        :rtype: OperationResult
        """
        url = "{0}/{1}".format(self.get_base_url(), project_entity.id)
        data = project_entity.to_json()

        response = self.nc.request(url, method="put", data=data, do_auth=True)
        return OperationResult(self, response)

    def delete(self, project_id):
        """ Deletes project.

        :param int project_id: project identifier
        :rtype: OperationResult
        """
        url = "{0}/{1}".format(self.get_base_url(), project_id)
        response = self.nc.request(url, method="delete", do_auth=True)
        return OperationResult(self, response, expected_status=204)

    def get_builds_handle(self):
        """
        :rtype: BuildHandle
        """
        return self.client.builds

    def get_build_tasks_handle(self):
        """
        :rtype: BuildTasksHandle
        """
        return self.client.build_tasks

    def get_project_chroots_handle(self):
        """
        :rtype: ProjectChrootHandle
        """
        return self.client.project_chroots


class ProjectChrootHandle(AbstractHandle):

    def get_base_url(self, project, **kwargs):
        """
        :type project: copr.client_v2.resources.Project
        """
        return "{0}{1}".format(self.root_url, project.get_href_by_name("chroots"))

    def get_one(self, project, name):
        """ Retrieves project chroot object.

        :type project: :py:class:`~copr.client_v2.resources.Project`
        :param project: parent project for the chroot
        :param str name: chroot name

        :rtype: :py:class:`~copr.client_v2.resources.ProjectChroot`
        """

        url = "{0}/{1}".format(self.get_base_url(project), name)
        response = self.nc.request(url)

        return ProjectChroot.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            project=project,
        )

    def get_list(self, project):
        """ Retrieves project chroot list object.

        :type project: :py:class:`~copr.client_v2.resources.Project`
        :param project: parent project for the chroot

        :rtype: :py:class:`~copr.client_v2.resources.ProjectChrootList`
        """
        response = self.nc.request(self.get_base_url(project))
        return ProjectChrootList.from_response(
            handle=self,
            response=response,
            project=project
        )

    def disable(self, project, name):
        """ Disables one chroot for the project

        :type project: :py:class:`~copr.client_v2.resources.Project`
        :param project: parent project for the chroot

        :param str name: chroot name to disable
        """
        url = "{0}/{1}".format(self.get_base_url(project), name)
        response = self.nc.request(url, method="DELETE", do_auth=True)
        return OperationResult(self, response)

    def enable(self, project, name, buildroot_pkgs=None):
        """ Enables one chroot for the project

        :type project: :py:class:`~copr.client_v2.resources.Project`
        :param project: parent project for the chroot

        :param str name: chroot name to enable

        :params buildroot_pkgs: packages to add into the buildroot
        :type buildroot_pkgs: list of str

        :rtype: :py:class:`.OperationResult`
        """

        new_entity = ProjectChrootEntity(
            name=name,
            buildroot_pkgs=buildroot_pkgs or list()
        )
        response = self.nc.request(
            self.get_base_url(project),
            method="POST",
            data=new_entity.to_json(),
            do_auth=True
        )
        return OperationResult(self, response)

    def update(self, project, chroot_entity):
        """
        :type project: copr.client_v2.resources.Project
        :param chroot_entity: Entity to update
        :type chroot_entity: :py:class:`.entities.ProjectChrootEntity`

        :rtype: :py:class:`.OperationResult`
        """
        url = "{0}/{1}".format(self.get_base_url(project), chroot_entity.name)
        response = self.nc.request(
            url,
            method="PUT",
            data=chroot_entity.to_json(),
            do_auth=True
        )
        return OperationResult(self, response)


class MockChrootHandle(AbstractHandle):

    def __init__(self, client, nc, root_url, href):
        super(MockChrootHandle, self).__init__(client, nc, root_url)
        self._href = href
        self._base_url = "{0}{1}".format(self.root_url, href)

    def get_base_url(self):
        return self._base_url

    def get_one(self, name):
        """ Retrieves mock chroot object.

        :param str name: chroot name

        :rtype: :py:class:`~copr.client_v2.resources.MockChroot`
        """
        url = "{0}/{1}".format(self.get_base_url(), name)
        response = self.nc.get(url)
        return MockChroot.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
        )

    def get_list(self, active_only=True):
        """ Retrieves mock chroot list object.

        :param bool active_only: when True, shows only chroots which can be used for builds

        :rtype: :py:class:`~copr.client_v2.resources.MockChrootList`
        """
        options = dict(active_only=active_only)

        response = self.nc.get(
            self.get_base_url(),
            query_params=options
        )
        return MockChrootList.from_response(
            handle=self,
            response=response,
            options=options
        )


def owner2user(owner):
    return owner and (owner if owner[0] != "@" else None)


def owner2group(owner):
    return owner and (owner[1:] if owner[0] == "@" else None)
