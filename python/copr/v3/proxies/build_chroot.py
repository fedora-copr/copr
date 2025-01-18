from __future__ import absolute_import

from . import BaseProxy
from ..requests import munchify
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class BuildChrootProxy(BaseProxy):
    def get(self, build_id, chrootname):
        """
        Return a build chroot

        :param int build_id:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/build-chroot"
        params = {
            "build_id": build_id,
            "chrootname": chrootname,
        }
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def get_list(self, build_id, pagination=None):
        """
        Return a list of build chroots

        :param int build_id:
        :param pagination:
        :return: Munch
        """
        endpoint = "/build-chroot/list"
        params = {
            "build_id": build_id,
        }
        params.update(pagination or {})
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def get_build_config(self, build_id, chrootname):
        """
        Return a build config for a build chroot

        :param int build_id:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/build-chroot/build-config"
        params = {
            "build_id": build_id,
            "chrootname": chrootname,
        }
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def get_built_packages(self, build_id, chrootname):
        """
        Return built packages (NEVRA dicts) for a given build chroot

        :param int build_id:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/build-chroot/built-packages"
        params = {
            "build_id": build_id,
            "chrootname": chrootname,
        }
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)
