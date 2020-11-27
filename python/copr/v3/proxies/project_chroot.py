from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, munchify, POST
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class ProjectChrootProxy(BaseProxy):

    def get(self, ownername, projectname, chrootname):
        """
        Return a configuration of a chroot in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/project-chroot"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    def get_build_config(self, ownername, projectname, chrootname):
        """
        Return a build configuration of a chroot in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/project-chroot/build-config"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return munchify(response)

    # pylint: disable=too-many-arguments
    def edit(self, ownername, projectname, chrootname, additional_packages=None, additional_repos=None,
             comps=None, delete_comps=False, with_opts=None, without_opts=None,
             bootstrap=None, bootstrap_image=None, isolation=None):
        """
        Edit a chroot configuration in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :param list additional_packages: buildroot packages for the chroot
        :param list additional_repos: buildroot additional additional_repos
        :param str comps: file path to the comps.xml file
        :param bool delete_comps: if True, current comps.xml will be removed
        :param list with_opts: Mock --with option
        :param list without_opts: Mock --without option
        :param str bootstrap: Allowed values 'on', 'off', 'image', 'default',
                              'untouched' (equivalent to None)
        :param str bootstrap_image: Implies 'bootstrap=image'.
        :param str isolation: Mock isolation feature setup.
            Possible values are 'default', 'simple', 'nspawn'.
        :return: Munch
        """
        endpoint = "/project-chroot/edit/{ownername}/{projectname}/{chrootname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }

        if bootstrap_image:
            bootstrap = 'custom_image'

        data = {
            "additional_repos": additional_repos,
            "additional_packages": additional_packages,
            "delete_comps": delete_comps,
            "with_opts": with_opts,
            "without_opts": without_opts,
            "bootstrap": bootstrap,
            "bootstrap_image": bootstrap_image,
            "isolation": isolation,
        }
        files = {}
        if comps:
            comps_f = open(comps, "rb")
            files["upload_comps"] = (os.path.basename(comps_f.name), comps_f, "application/text")

        request = FileRequest(endpoint, api_base_url=self.api_base_url, method=POST,
                              params=params, data=data, files=files, auth=self.auth)
        response = request.send()
        return munchify(response)
