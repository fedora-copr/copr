from __future__ import absolute_import

from . import BaseProxy
from ..requests import Request, munchify, POST, GET, PUT


class ProjectProxy(BaseProxy):

    def get(self, ownername, projectname):
        """
        Return a project

        :param str ownername:
        :param str projectname:
        :return: Munch
        """
        endpoint = "/project"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def get_list(self, ownername=None, pagination=None):
        """
        Return a list of projects

        :param str ownername:
        :param pagination:
        :return: Munch
        """
        endpoint = "/project/list"
        params = {
            "ownername": ownername,
        }
        params.update(pagination or {})
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def search(self, query, pagination=None):
        """
        Return a list of projects based on fulltext search

        :param str query:
        :param pagination:
        :return: Munch
        """
        endpoint = "/project/search"
        params = {
            "query": query,
        }
        params.update(pagination or {})
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def add(self, ownername, projectname, chroots, description=None, instructions=None, homepage=None,
            contact=None, additional_repos=None, unlisted_on_hp=False, enable_net=True, persistent=False,
            auto_prune=True, use_bootstrap_container=False, devel_mode=False,
            delete_after_days=None):
        """
        Create a project

        :param str ownername:
        :param str projectname:
        :param list chroots:
        :param str description:
        :param str instructions:
        :param str homepage:
        :param str contact:
        :param list additional_repos:
        :param bool unlisted_on_hp: project will not be shown on Copr homepage
        :param bool enable_net: if builder can access net for builds in this project
        :param bool persistent: if builds and the project are undeletable
        :param bool auto_prune: if backend auto-deletion script should be run for the project
        :param bool use_bootstrap_container: if mock bootstrap container is used to initialize the buildroot
        :param bool devel_mode: if createrepo should run automatically
        :param int delete_after_days: delete the project after the specfied period of time
        :return: Munch
        """
        endpoint = "/project/add/{ownername}"
        params = {
            "ownername": ownername,
        }
        data = {
            "name": projectname,
            "chroots": chroots,
            "description": description,
            "instructions": instructions,
            "homepage": homepage,
            "contact": contact,
            "additional_repos": additional_repos,
            "unlisted_on_hp": unlisted_on_hp,
            "enable_net": enable_net,
            "persistent": persistent,
            "auto_prune": auto_prune,
            "use_bootstrap_container": use_bootstrap_container,
            "devel_mode": devel_mode,
            "delete_after_days": delete_after_days,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def edit(self, ownername, projectname, chroots=None, description=None, instructions=None, homepage=None,
             contact=None, additional_repos=None, unlisted_on_hp=None, enable_net=None,
             auto_prune=None, use_bootstrap_container=None, devel_mode=None,
             delete_after_days=None):
        """
        Edit a project

        :param str ownername:
        :param str projectname:
        :param list chroots:
        :param str description:
        :param str instructions:
        :param str homepage:
        :param str contact:
        :param list repos:
        :param bool unlisted_on_hp: project will not be shown on Copr homepage
        :param bool enable_net: if builder can access net for builds in this project
        :param bool auto_prune: if backend auto-deletion script should be run for the project
        :param bool use_bootstrap_container: if mock bootstrap container is used to initialize the buildroot
        :param bool devel_mode: if createrepo should run automatically
        :param int delete_after_days: delete the project after the specfied period of time
        :return: Munch
        """
        endpoint = "/project/edit/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "chroots": chroots,
            "description": description,
            "instructions": instructions,
            "homepage": homepage,
            "contact": contact,
            "repos": additional_repos,
            "unlisted_on_hp": unlisted_on_hp,
            "enable_net": enable_net,
            "auto_prune": auto_prune,
            "use_bootstrap_container": use_bootstrap_container,
            "devel_mode": devel_mode,
            "delete_after_days": delete_after_days,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def delete(self, ownername, projectname):
        """
        Delete a project

        :param str ownername:
        :param str projectname:
        :return: Munch
        """
        endpoint = "/project/delete/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "verify": True,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def fork(self, ownername, projectname, dstownername, dstprojectname, confirm=False):
        """
        Fork a project

        :param str ownername: owner of a source project
        :param str projectname: name of a source project
        :param str dstownername: owner of a destination project
        :param str dstprojectname: name of a destination project
        :param bool confirm: if forking into a existing project, this needs to be set to True,
                             to confirm that user is aware of that
        :return: Munch
        """
        endpoint = "/project/fork/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        data = {
            "name": dstprojectname,
            "ownername": dstownername,
            "confirm": confirm,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, method=POST,
                          params=params, data=data, auth=self.auth)
        response = request.send()
        return munchify(response)

    def get_permissions(self, ownername, projectname):
        """
        Get project permissions

        :param str ownername: owner of the project
        :param str projectname: name of the project
        :return Munch: a dictionary in format
            ``{username: {permission: state, ... }, ...}`` where ``username``
            identifies an existing copr user, ``permission`` is one of
            ``admin|builder`` and state is one of ``nothing|approved|request``.
        """

        endpoint = "/project/permissions/get/{ownername}/{projectname}/"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        request = Request(
                endpoint,
                api_base_url=self.api_base_url,
                auth=self.auth,
                method=GET,
                params=params)

        response = request.send()
        return munchify(response)

    def set_permissions(self, ownername, projectname, permissions):
        """
        Set (or change) permissions for a project

        :param str ownername: owner of the updated project
        :param str projectname: name of the updated project
        :param dict permissions: the expected format is
            ``{username: {permission: state, ...}, ...}``
            where ``username`` identifies an existing copr user, ``permission``
            is one of ``builder|admin`` and ``state`` value is one of
            ``nothing|request|approved``.  It is OK to set only ``bulider`` or
            only ``admin`` permission; any unspecified ``permission`` is then
            (a) set to ``nothing`` (if the permission entry is newly created),
            or (b) kept unchanged (if an existing permission entry is edited).
            If more than one ``username`` is specified in single
            ``set_permissions()`` request, the approach is to configure
            *all-or-nothing* (any error makes the whole operation fail and
            no-op).
        """

        endpoint = "/project/permissions/set/{ownername}/{projectname}/"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        request = Request(
                endpoint,
                api_base_url=self.api_base_url,
                auth=self.auth,
                method=PUT,
                params=params,
                data=permissions)

        request.send()

    def request_permissions(self, ownername, projectname, permissions):
        """
        Request/cancel request/drop your permissions on project

        :param str ownername: owner of the requested project
        :param str projectname: name of the requested project
        :param dict permissions: the desired permissions user wants to have on
            the requested copr project.  The format is
            ``{permission: bool, ...}``, where ``permission`` is one of
            ``builder|admin`` and ``bool`` is
            (a) ``True`` for *requesting* the role or
            (b) ``False`` for *dropping* the role (or for *cancelling* of
            previous request).
        """
        endpoint = "/project/permissions/request/{ownername}/{projectname}/"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        request = Request(
                endpoint,
                api_base_url=self.api_base_url,
                auth=self.auth,
                method=PUT,
                params=params,
                data=permissions)

        request.send()
