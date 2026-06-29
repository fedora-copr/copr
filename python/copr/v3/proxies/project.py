from __future__ import absolute_import

import warnings
from enum import Enum
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from munch import Munch

from . import BaseProxy
from ..requests import munchify, DELETE, POST, PUT
from ..helpers import for_all_methods, bind_proxy


class PermissionState(Enum):
    """
    Possible values that user can have or set for their `builder` and `admin`
    permissions on some project.
    """
    NOTHING = "nothing"
    REQUEST = "request"
    APPROVED = "approved"


class Permissions(TypedDict, total=False):
    """
    A set of permissions that a user has or wants to have for some project
    """
    builder: PermissionState
    admin: PermissionState


# The `str` keys are usernames
UserPermissions = Dict[str, Permissions]


class OrderType(Enum):
    """
    Order items in ascending or descending order
    """
    ASC = "ASC"
    DESC = "DESC"


class PaginationMeta(TypedDict, total=False):
    """
    How should the results be paginated?
    More information here:
    https://python-copr.readthedocs.io/en/latest/client_v3/pagination.html
    """
    offset: int
    limit: Optional[int]
    order: str
    order_type: OrderType


def _compat_use_bootstrap_container(
    data: Dict[str, Any],
    value: Optional[bool],
) -> None:
    if value is None:
        return
    data["bootstrap"] = "on" if value else "off"
    warnings.warn("The 'use_bootstrap_container' argument is obsoleted by "
                  "'bootstrap' and 'bootstrap_image'")


@for_all_methods(bind_proxy)
class ProjectProxy(BaseProxy):

    def get(self, ownername: str, projectname: str) -> Munch:
        """
        Return a project

        :param ownername:
        :param projectname:
        :return: Munch
        """
        endpoint = "/project"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def get_list(
        self,
        ownername: Optional[str] = None,
        pagination: Optional[PaginationMeta] = None,
    ) -> Munch:
        """
        Return a list of projects

        :param ownername:
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

    def search(
        self,
        query: str,
        pagination: Optional[PaginationMeta] = None,
    ) -> Munch:
        """
        Return a list of projects based on fulltext search

        :param query:
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

    def add(
        self,
        ownername: str,
        projectname: str,
        chroots: List[str],
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        homepage: Optional[str] = None,
        contact: Optional[str] = None,
        additional_repos: Optional[List[str]] = None,
        unlisted_on_hp: bool = False,
        enable_net: bool = False,
        persistent: bool = False,
        auto_prune: bool = True,
        use_bootstrap_container: Optional[bool] = None,
        devel_mode: bool = False,
        delete_after_days: Optional[int] = None,
        multilib: bool = False,
        module_hotfixes: bool = False,
        bootstrap: Optional[str] = None,
        bootstrap_image: Optional[str] = None,
        isolation: Optional[str] = None,
        follow_fedora_branching: bool = True,
        fedora_review: Optional[bool] = None,
        appstream: bool = False,
        runtime_dependencies: Optional[str] = None,
        packit_forge_projects_allowed: Optional[List[str]] = None,
        repo_priority: Optional[int] = None,
        exist_ok: bool = False,
        storage: Optional[str] = None,
    ) -> Munch:
        """
        Create a project

        :param ownername:
        :param projectname:
        :param chroots:
        :param description:
        :param instructions:
        :param homepage:
        :param contact:
        :param additional_repos:
        :param unlisted_on_hp: project will not be shown on Copr homepage
        :param enable_net: if builder can access net for builds in this project
        :param persistent: if builds and the project are undeletable
        :param auto_prune: if backend auto-deletion script should be run for the project
        :param use_bootstrap_container: obsoleted, use the 'bootstrap'
            argument and/or the 'bootstrap_image'.
        :param devel_mode: if createrepo should run automatically
        :param delete_after_days: delete the project after the specfied period of time
        :param module_hotfixes: allow packages from this project to
                                     override packages from active module streams.
        :param bootstrap: Mock bootstrap feature setup.
            Possible values are 'default', 'on', 'off', 'image'.
        :param bootstrap_image: Name of the container image to initialize
            the bootstrap chroot from.  This also implies 'bootstrap=image'.
            This is a noop parameter and its value is ignored.
        :param isolation: Mock isolation feature setup.
            Possible values are 'default', 'simple', 'nspawn'.
        :param follow_fedora_branching: If newly branched chroots should be automatically enabled and populated
        :param fedora_review: Run fedora-review tool for packages
                                   in this project
        :param appstream: Disable or enable generating the appstream metadata
        :param runtime_dependencies: List of external repositories
            (== dependencies, specified as baseurls) that will be automatically
            enabled together with this project repository.
        :param packit_forge_projects_allowed: List of forge projects that
            will be allowed to build in the project via Packit
        :param storage: Admin only - What storage should be used for this project
        :return: Munch
        """
        endpoint = "/project/add/{ownername}"
        params = {
            "ownername": ownername,
            "exist_ok": exist_ok,
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
            "storage": storage,
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

    def edit(
        self,
        ownername: str,
        projectname: str,
        chroots: Optional[List[str]] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        homepage: Optional[str] = None,
        contact: Optional[str] = None,
        additional_repos: Optional[List[str]] = None,
        unlisted_on_hp: Optional[bool] = None,
        enable_net: Optional[bool] = None,
        auto_prune: Optional[bool] = None,
        use_bootstrap_container: Optional[bool] = None,
        devel_mode: Optional[bool] = None,
        delete_after_days: Optional[int] = None,
        multilib: Optional[bool] = None,
        module_hotfixes: Optional[bool] = None,
        bootstrap: Optional[str] = None,
        bootstrap_image: Optional[str] = None,
        isolation: Optional[str] = None,
        follow_fedora_branching: Optional[bool] = None,
        fedora_review: Optional[bool] = None,
        appstream: Optional[bool] = None,
        runtime_dependencies: Optional[str] = None,
        packit_forge_projects_allowed: Optional[List[str]] = None,
        repo_priority: Optional[int] = None,
    ) -> Munch:
        """
        Edit a project

        :param ownername:
        :param projectname:
        :param chroots:
        :param description:
        :param instructions:
        :param homepage:
        :param contact:
        :param repos:
        :param unlisted_on_hp: project will not be shown on Copr homepage
        :param enable_net: if builder can access net for builds in this project
        :param auto_prune: if backend auto-deletion script should be run for the project
        :param use_bootstrap_container: obsoleted, use the 'bootstrap'
            argument and/or the 'bootstrap_image'.
        :param devel_mode: if createrepo should run automatically
        :param delete_after_days: delete the project after the specfied period of time
        :param module_hotfixes: allow packages from this project to
                                     override packages from active module streams.
        :param bootstrap: Mock bootstrap feature setup.
            Possible values are 'default', 'on', 'off', 'image'.
        :param isolation: Mock isolation feature setup.
            Possible values are 'default', 'simple', 'nspawn'.
        :param follow_fedora_branching: If newly branched chroots should be automatically enabled and populated.
        :param bootstrap_image: Name of the container image to initialize
            the bootstrap chroot from.  This also implies 'bootstrap=image'.
            This is a noop parameter and its value is ignored.
        :param fedora_review: Run fedora-review tool for packages
                                   in this project
        :param appstream: Disable or enable generating the appstream metadata
        :param runtime_dependencies: List of external repositories
            (== dependencies, specified as baseurls) that will be automatically
            enabled together with this project repository.
        :param packit_forge_projects_allowed: List of forge projects that
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
            method=PUT,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def delete(self, ownername: str, projectname: str) -> Munch:
        """
        Delete a project

        :param ownername:
        :param projectname:
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
            method=DELETE,
            params=params,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def fork(
        self,
        ownername: str,
        projectname: str,
        dstownername: str,
        dstprojectname: str,
        confirm: bool = False,
    ) -> Munch:
        """
        Fork a project

        :param ownername: owner of a source project
        :param projectname: name of a source project
        :param dstownername: owner of a destination project
        :param dstprojectname: name of a destination project
        :param confirm: if forking into a existing project, this needs to be set to True,
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

    def can_build_in(self, who: str, ownername: str, projectname: str) -> bool:
        """
        Return ``True`` a user can submit builds for a ownername/projectname

        :param who: name of the user checking their permissions
        :param ownername: owner of the project
        :param projectname: name of the project
        :return: ``True`` or raise
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

    def get_permissions(self, ownername: str, projectname: str) -> Munch:
        """
        Get project permissions

        :param ownername: owner of the project
        :param projectname: name of the project
        :return: a dictionary in format
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

    def set_permissions(
        self,
        ownername: str,
        projectname: str,
        permissions: UserPermissions,
    ) -> None:
        """
        Set (or change) permissions for a project

        :param ownername: owner of the updated project
        :param projectname: name of the updated project
        :param permissions: the expected format is
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

    def request_permissions(
        self,
        ownername: str,
        projectname: str,
        permissions: Permissions,
    ) -> None:
        """
        Request/cancel request/drop your permissions on project

        :param ownername: owner of the requested project
        :param projectname: name of the requested project
        :param permissions: the desired permissions user wants to have on
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

    def regenerate_repos(self, ownername: str, projectname: str) -> Munch:
        """
        Regenerate repositories for a project

        :param ownername: owner of the project to regenerate
        :param projectname: name of the project to regenerate
        """
        endpoint = "/project/regenerate-repos/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname
        }
        response = self.request.send(
            endpoint=endpoint, method=PUT, params=params, auth=self.auth)
        return munchify(response)
