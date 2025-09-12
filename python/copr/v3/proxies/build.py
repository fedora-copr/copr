from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import FileRequest, munchify, DELETE, POST, PUT
from ..exceptions import CoprValidationException
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class BuildProxy(BaseProxy):
    def get(self, build_id):
        """
        Return a build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/{0}".format(build_id)
        response = self.request.send(endpoint=endpoint)
        return munchify(response)

    def get_source_chroot(self, build_id):
        """
        Return a source build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/source-chroot/{0}".format(build_id)
        response = self.request.send(endpoint=endpoint)
        return munchify(response)

    def get_source_build_config(self, build_id):
        """
        Return a config for source build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/source-build-config/{0}".format(build_id)
        response = self.request.send(endpoint=endpoint)
        return munchify(response)

    def get_built_packages(self, build_id):
        """
        Return built packages (NEVRA dicts) for a given build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/built-packages/{0}".format(build_id)
        response = self.request.send(endpoint=endpoint)
        return munchify(response)

    def get_list(self, ownername, projectname, packagename=None, status=None, pagination=None):
        """
        Return a list of packages

        :param str ownername:
        :param str projectname:
        :param str packagename:
        :param str status:
        :param pagination:
        :return: Munch
        """
        endpoint = "/build/list"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "packagename": packagename,
            "status": status,
        }
        params.update(pagination or {})

        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)

    def cancel(self, build_id):
        """
        Cancel a build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/cancel/{0}".format(build_id)
        response = self.request.send(
            endpoint=endpoint, method=PUT, auth=self.auth)
        return munchify(response)

    def create_from_urls(self, ownername, projectname, urls, buildopts=None, project_dirname=None):
        """
        Create builds from a list of URLs

        :param str ownername:
        :param str projectname:
        :param list urls:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/url"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "pkgs": urls,
            "project_dirname": project_dirname,
        }
        return self._create(endpoint, data, buildopts=buildopts)

    def create_from_url(self, ownername, projectname, url, buildopts=None, project_dirname=None):
        """
        Create a build from URL

        :param str ownername:
        :param str projectname:
        :param str url:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        if len(url.split()) > 1:
            raise CoprValidationException("This method doesn't allow submitting multiple URLs at once. "
                                          "Use `create_from_urls` instead.")
        return self.create_from_urls(ownername, projectname, [url], buildopts=buildopts,
                                     project_dirname=project_dirname)[0]

    def create_from_file(self, ownername, projectname, path, buildopts=None, project_dirname=None):
        """
        Create a build from local SRPM file

        :param str ownername:
        :param str projectname:
        :param str path:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/upload"
        f = open(path, "rb")

        data = {
            "ownername": ownername,
            "projectname": projectname,
            "project_dirname": project_dirname,
        }
        files = {
            "pkgs": (os.path.basename(f.name), f, "application/x-rpm"),
        }
        return self._create(endpoint, data, files=files, buildopts=buildopts)

    def check_before_build(self, ownername, projectname,
                           project_dirname=None, buildopts=None):
        """
        Check if a build can be submitted (if the project exists, you have
        permissions, the chroot exists, etc). This is useful before trying to
        upload a large SRPM and failing to do so.

        :param str ownername:
        :param str projectname:
        :param str project_dirname:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :return: Munch
        """
        endpoint = "/build/check-before-build"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "project_dirname": project_dirname,
        }

        del buildopts["progress_callback"]
        data.update(buildopts or {})

        response = self.request.send(
            endpoint=endpoint,
            method=POST,
            data=data,
            auth=self.auth,
        )
        return munchify(response)

    def create_from_scm(self, ownername, projectname, clone_url, committish="", subdirectory="", spec="",
                        scm_type="git", source_build_method="rpkg", buildopts=None, project_dirname=None):
        """
        Create a build from SCM repository

        :param str ownername:
        :param str projectname:
        :param str clone_url: url to a project versioned by Git or SVN
        :param str committish: name of a branch, tag, or a git hash
        :param str subdirectory: path to a subdirectory with package content
        :param str spec: path to spec file, relative to 'subdirectory'
        :param str scm_type:
        :param str source_build_method:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/scm"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "clone_url": clone_url,
            "committish": committish,
            "subdirectory": subdirectory,
            "spec": spec,
            "scm_type": scm_type,
            "source_build_method": source_build_method,
            "project_dirname": project_dirname,
        }
        return self._create(endpoint, data, buildopts=buildopts)

    def create_from_distgit(self, ownername, projectname, packagename,
                            committish=None, namespace=None, distgit=None,
                            buildopts=None, project_dirname=None):
        """
        Create a build from a DistGit repository

        :param str ownername:
        :param str projectname:
        :param str packagename: the DistGit package name to build
        :param str committish: name of a branch, tag, or a git hash
        :param str namespace: DistGit namespace, e.g. '@copr/copr' for
            the '@copr/copr/copr-cli' package
        :param str distgit: the DistGit instance name we build against,
            for example 'fedora'.  Optional, and the default is deployment
            specific.
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/distgit"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "distgit": distgit,
            "namespace": namespace,
            "package_name": packagename,
            "committish": committish,
            "project_dirname": project_dirname,
        }
        return self._create(endpoint, data, buildopts=buildopts)


    def create_from_pypi(self, ownername, projectname, pypi_package_name,
                         pypi_package_version=None, spec_template='',
                         python_versions=None, buildopts=None,
                         project_dirname=None, spec_generator=None):
        """
        Create a build from PyPI - https://pypi.org/

        :param str ownername:
        :param str projectname:
        :param str pypi_package_name:
        :param str pypi_package_version: PyPI package version (None means "latest")
        :param str spec_template: what pyp2rpm spec template to use
        :param list python_versions: list of python versions to build for
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :param str spec_generator: what tool should be used for spec generation
        :return: Munch
        """
        endpoint = "/build/create/pypi"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "pypi_package_name": pypi_package_name,
            "pypi_package_version": pypi_package_version,
            "spec_generator": spec_generator,
            "spec_template": spec_template,
            "python_versions": python_versions or [3, 2],
            "project_dirname": project_dirname,
        }
        return self._create(endpoint, data, buildopts=buildopts)

    def create_from_rubygems(self, ownername, projectname, gem_name, buildopts=None, project_dirname=None):
        """
        Create a build from RubyGems - https://rubygems.org/

        :param str ownername:
        :param str projectname:
        :param str gem_name:
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/rubygems"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "gem_name": gem_name,
            "project_dirname": project_dirname,
        }
        return self._create(endpoint, data, buildopts=buildopts)

    def create_from_custom(self, ownername, projectname, script, script_chroot=None,
                           script_builddeps=None, script_resultdir=None, script_repos=None,
                           buildopts=None, project_dirname=None):
        """
        Create a build from custom script.

        :param str ownername:
        :param str projectname:
        :param script: script to execute to generate sources
        :param script_chroot: [optional] what chroot to use to generate
            sources (defaults to fedora-latest-x86_64)
        :param script_builddeps: [optional] list of script's dependencies
        :param script_resultdir: [optional] where script generates results
            (relative to cwd)
        :parm script_repos: [optional] external repositories containing script's
            dependencies
        :param buildopts: http://python-copr.readthedocs.io/en/latest/client_v3/build_options.html
        :param str project_dirname:
        :return: Munch
        """
        endpoint = "/build/create/custom"
        data = {
            "ownername": ownername,
            "projectname": projectname,
            "script": script,
            "chroot": script_chroot,
            "builddeps": script_builddeps,
            "resultdir": script_resultdir,
            "project_dirname": project_dirname,
            "repos": script_repos,
        }
        return self._create(endpoint, data, buildopts=buildopts)

    def _create(self, endpoint, data, files=None, buildopts=None):
        data = data.copy()

        kwargs = {"api_base_url": self.api_base_url}
        if files and buildopts and "progress_callback" in buildopts:
            kwargs["progress_callback"] = buildopts["progress_callback"]
            del buildopts["progress_callback"]

        data.update(buildopts or {})
        if not files:
            response = self.request.send(
                endpoint=endpoint, data=data, method=POST, auth=self.auth)
        else:
            kwargs["files"] = files
            kwargs["connection_attempts"] = self.config.get("connection_attempts", 1)
            request = FileRequest(**kwargs)
            response = request.send(
                endpoint=endpoint, data=data, method=POST, auth=self.auth)
        return munchify(response)

    def delete(self, build_id):
        """
        Delete a build

        :param int build_id:
        :return: Munch
        """
        endpoint = "/build/delete/{0}".format(build_id)
        response = self.request.send(
            endpoint=endpoint, method=DELETE, auth=self.auth)
        return munchify(response)

    def delete_list(self, build_ids):
        """
        Delete multiple builds specified by a list of their ids.

        :param list[int] build_id:
        :return: Munch
        """

        endpoint = "/build/delete/list"
        data = {"builds": build_ids}
        response = self.request.send(
            endpoint=endpoint, data=data, method=DELETE, auth=self.auth)
        return munchify(response)
