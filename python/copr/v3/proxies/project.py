from __future__ import absolute_import

from . import BaseProxy
from ..requests import Request, munchify, POST


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
