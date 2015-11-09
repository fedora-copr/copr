# coding: utf-8
from abc import abstractmethod, ABCMeta
import json
import os

from copr.client_v2.net_client import RequestError, MultiPartTuple
from .entities import ProjectChrootEntity
from .resources import Project, OperationResult, ProjectsList, ProjectChroot, ProjectChrootList, Build, BuildList, \
    MockChroot, MockChrootList


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
        self._base_url = "{}{}".format(self.root_url, builds_href)

    def get_base_url(self):
        return self._base_url

    def get_one(self, build_id):
        """
        :type build_id: int
        """

        options = {"build_id": build_id}
        url = "{}/{}".format(self.get_base_url(), build_id)
        response = self.nc.request(url)
        return Build.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            options=options,
        )

    def get_list(self, project_id=None, owner=None, limit=None, offset=None):
        """
        :param owner:
        :param project_id:
        :param limit:
        :param offset:
        :rtype: BuildList
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
        """
        :type build_entity: copr.client_v2.entities.BuildEntity
        """
        build_id = build_entity.id
        build_entity.state = "canceled"

        url = "{}/{}".format(self.get_base_url(), build_id)
        response = self.nc.request(url, data=build_entity.to_json(), method="PUT", do_auth=True)
        return OperationResult(self, response)

    def delete(self, build_id):
        url = "{}/{}".format(self.get_base_url(), build_id)
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

        chroots = map(str, chroots or list())
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

    def create_from_file(self, project_id, file_path=None, file_obj=None, file_name=None,
                         chroots=None, enable_net=True):
        """
        Creates new build using srpm upload, please specify
        either `file_path` or (`file_obj`, `file_name).

        :param int project_id:
        :param str file_path: path to the srpm file
        :param file like object file_obj:
        :param str file_name:
        :param list chroots:
        :param bool enable_net:
        :return: created build
        :rtype: Build
        """

        chroots = map(str, chroots or list())
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


class ProjectHandle(AbstractHandle):

    def __init__(self, client, nc, root_url, projects_href):
        super(ProjectHandle, self).__init__(client, nc, root_url)
        self.projects_href = projects_href
        self._base_url = "{}{}".format(self.root_url, projects_href)

    def get_base_url(self):
        return self._base_url

    def get_list(self, search_query=None, owner=None, name=None, limit=None, offset=None):
        """
        :param search_query:
        :param owner:
        :param name:
        :param limit:
        :param offset:
        :rtype: ProjectsList
        """
        options = {
            "search_query": search_query,
            "owner": owner,
            "name": name,
            "limit": limit,
            "offset": offset
        }

        response = self.nc.request(self.get_base_url(), query_params=options)
        return ProjectsList.from_response(self, response, options)

    def get_one(self, project_id, show_builds=False, show_chroots=False):
        """
        :type project_id: int
        """
        query_params = {
            "show_builds": show_builds,
            "show_chroots": show_chroots
        }
        # import ipdb; ipdb.set_trace()
        url = "{}/{}".format(self.get_base_url(), project_id)
        response = self.nc.request(url, query_params=query_params)
        return Project.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            options=query_params
        )

    def update(self, project_entity):
        """
        :type project_entity: ProjectEntity
        """
        url = "{}/{}".format(self.get_base_url(), project_entity.id)
        data = project_entity.to_json()

        response = self.nc.request(url, method="put", data=data, do_auth=True)
        return OperationResult(self, response)

    def delete(self, project_id):
        url = "{}/{}".format(self.get_base_url(), project_id)
        response = self.nc.request(url, method="delete", do_auth=True)
        return OperationResult(self, response, expected_status=204)

    def get_builds_handle(self):
        """
        :rtype: BuildHandle
        """
        return self.client.builds

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
        return "{}{}".format(self.root_url, project.get_href_by_name("chroots"))

    def get_one(self, project, name):
        """
        :type project: copr.client_v2.resources.Project
        :param str name: chroot name
        """

        url = "{}/{}".format(self.get_base_url(project), name)
        response = self.nc.request(url)

        return ProjectChroot.from_response(
            handle=self,
            response=response,
            data_dict=response.json,
            project=project,
        )

    def get_list(self, project):
        """
        :type project: copr.client_v2.resources.Project
        """
        response = self.nc.request(self.get_base_url(project))
        return ProjectChrootList.from_response(
            handle=self,
            response=response,
            project=project
        )

    def disable(self, project, name):
        """
        :type project: copr.client_v2.resources.Project
        :param str name: chroot name to disable
        """
        url = "{}/{}".format(self.get_base_url(project), name)
        response = self.nc.request(url, method="DELETE", do_auth=True)
        return OperationResult(self, response)

    def enable(self, project, name, buildroot_pkgs=None):
        """
        :type project: copr.client_v2.resources.Project
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
        :type chroot_entity: copr.client_v2.entities.ProjectChrootEntity
        """
        url = "{}/{}".format(self.get_base_url(project), chroot_entity.name)
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
        self._base_url = "{}{}".format(self.root_url, href)

    def get_base_url(self):
        return self._base_url

    def get_one(self, name):
        url = "{}/{}".format(self.get_base_url(), name)
        response = self.nc.get(url)
        return MockChroot.from_response(self, response, response.json)

    def get_list(self, active_only=True):
        options = dict(active_only=active_only)

        response = self.nc.get(
            self.get_base_url(),
            query_params=options
        )
        return MockChrootList.from_response(
            handle=self,
            response=response,
            options=options)
