from __future__ import absolute_import

import warnings

from . import BaseProxy
from ..requests import munchify, POST, GET, PUT
from ..helpers import for_all_methods, bind_proxy


def _compat_use_bootstrap_container(data, value):
    if value is None:
        return
    data["bootstrap"] = "on" if value else "off"
    warnings.warn("The 'use_bootstrap_container' argument is obsoleted by "
                  "'bootstrap' and 'bootstrap_image'")


@for_all_methods(bind_proxy)
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
        response = self.request.send(endpoint=endpoint, params=params)
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
        response = self.request.send(endpoint=endpoint, params=params)
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
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def add(self, ownername, projectname, chroots, description=None, instructions=None, homepage=None,
            contact=None, additional_repos=None, unlisted_on_hp=False, enable_net=False, persistent=False,
            auto_prune=True, use_bootstrap_container=None, devel_mode=False,
            delete_after_days=None, multilib=False, module_hotfixes=False,
            bootstrap=None, bootstrap_image=None, isolation=None, follow_fedora_branching=True,
            fedora_review=None, appstream=False, runtime_dependencies=None, packit_forge_projects_allowed=None,
            repo_priority=None):
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
        :param bool use_bootstrap_container: obsoleted, use the 'bootstrap'
            argument and/or the 'bootstrap_image'.
        :param bool devel_mode: if createrepo should run automatically
        :param int delete_after_days: delete the project after the specfied period of time
        :param bool module_hotfixes: allow packages from this project to
                                     override packages from active module streams.
        :param str bootstrap: Mock bootstrap feature setup.
            Possible values are 'default', 'on', 'off', 'image'.
        :param str bootstrap_image: Name of the container image to initialize
            the bootstrap chroot from.  This also implies 'bootstrap=image'.
            This is a noop parameter and its value is ignored.
        :param str isolation: Mock isolation feature setup.
            Possible values are 'default', 'simple', 'nspawn'.
        :param bool follow_fedora_branching: If newly branched chroots should be automatically enabled and populated
        :param bool fedora_review: Run fedora-review tool for packages
                                   in this project
        :param bool appstream: Disable or enable generating the appstream metadata
        :param string runtime_dependencies: List of external repositories
            (== dependencies, specified as baseurls) that will be automatically
            enabled together with this project repository.
        :param list packit_forge_projects_allowed: List of forge projects that
            will be allowed to build in the project via Packit
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
            "bootstrap": bootstrap,
            "bootstrap_image": bootstrap_image,
            "isolation": isolation,
            "follow_fedora_branching": follow_fedora_branching,
            "devel_mode": devel_mode,
            "delete_after_days": delete_after_days,
            "multilib": multilib,
            "module_hotfixes": module_hotfixes,
            "fedora_review": fedora_review,
            "appstream": appstream,
            "runtime_dependencies": runtime_dependencies,
            "packit_forge_projects_allowed": packit_forge_projects_allowed,
            "repo_priority": repo_priority,
        }

        _compat_use_bootstrap_container(data, use_bootstrap_container)

        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def edit(self, ownername, projectname, chroots=None, description=None, instructions=None, homepage=None,
             contact=None, additional_repos=None, unlisted_on_hp=None, enable_net=None,
             auto_prune=None, use_bootstrap_container=None, devel_mode=None,
             delete_after_days=None, multilib=None, module_hotfixes=None,
             bootstrap=None, bootstrap_image=None, isolation=None, follow_fedora_branching=None,
             fedora_review=None, appstream=None, runtime_dependencies=None, packit_forge_projects_allowed=None,
             repo_priority=None):
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
        :param bool use_bootstrap_container: obsoleted, use the 'bootstrap'
            argument and/or the 'bootstrap_image'.
        :param bool devel_mode: if createrepo should run automatically
        :param int delete_after_days: delete the project after the specfied period of time
        :param bool module_hotfixes: allow packages from this project to
                                     override packages from active module streams.
        :param str bootstrap: Mock bootstrap feature setup.
            Possible values are 'default', 'on', 'off', 'image'.
        :param str isolation: Mock isolation feature setup.
            Possible values are 'default', 'simple', 'nspawn'.
        :param bool follow_fedora_branching: If newly branched chroots should be automatically enabled and populated.
        :param str bootstrap_image: Name of the container image to initialize
            the bootstrap chroot from.  This also implies 'bootstrap=image'.
            This is a noop parameter and its value is ignored.
        :param bool fedora_review: Run fedora-review tool for packages
                                   in this project
        :param bool appstream: Disable or enable generating the appstream metadata
        :param string runtime_dependencies: List of external repositories
            (== dependencies, specified as baseurls) that will be automatically
            enabled together with this project repository.
        :param list packit_forge_projects_allowed: List of forge projects that
            will be allowed to build in the project via Packit
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
            "bootstrap": bootstrap,
            "isolation": isolation,
            "follow_fedora_branching": follow_fedora_branching,
            "bootstrap_image": bootstrap_image,
            "devel_mode": devel_mode,
            "delete_after_days": delete_after_days,
            "multilib": multilib,
            "module_hotfixes": module_hotfixes,
            "fedora_review": fedora_review,
            "appstream": appstream,
            "runtime_dependencies": runtime_dependencies,
            "packit_forge_projects_allowed": packit_forge_projects_allowed,
            "repo_priority": repo_priority,
        }

        _compat_use_bootstrap_container(data, use_bootstrap_container)

        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
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
        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
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
        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def can_build_in(self, who, ownername, projectname):
        """
        Return `True` a user can submit builds for a ownername/projectname

        :param str who: name of the user checking their permissions
        :param str ownername: owner of the project
        :param str projectname: name of the project
        :return Bool: `True` or raise
        """
        endpoint = ("/project/permissions/can_build_in/"
                    "{who}/{ownername}/{projectname}/")
        params = {
            "who": who,
            "ownername": ownername,
            "projectname": projectname,
        }
        response = self.request.send(
            endpoint=endpoint,
            params=params,
            auth=self.auth
        )
        return munchify(response).can_build_in

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
        response = self.request.send(
            endpoint=endpoint, params=params, auth=self.auth)
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
        self.request.send(
            endpoint=endpoint,
            method=PUT,
            params=params,
            data=permissions,
            auth=self.auth,
        )

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
        self.request.send(
            endpoint=endpoint,
            method=PUT,
            params=params,
            data=permissions,
            auth=self.auth,
        )

    def regenerate_repos(self, ownername, projectname):
        """
        Regenerate repositories for a project

        :param str ownername: owner of the project to regenerate
        :param str projectname: name of the project to regenerate
        """
        endpoint = "/project/regenerate-repos/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname
        }
        response = self.request.send(
            endpoint=endpoint, method=PUT, params=params, auth=self.auth)
        return munchify(response)
