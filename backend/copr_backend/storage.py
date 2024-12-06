"""
Support for various data storages, e.g. results directory on backend, Pulp, etc.
"""

import os
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, as_completed
# We need to stop using the deprecated distutils module.
# See https://peps.python.org/pep-0632/
# As of Python 3.12, it doesn't even exist now, we just use an alias provided
# by python3-setutpools, see
# https://fedoraproject.org/wiki/Changes/Python3.12#The_Python_standard_library_distutils_module_will_be_removed
from distutils.dir_util import copy_tree  # pylint: disable=deprecated-module
from distutils.errors import DistutilsFileError # pylint: disable=deprecated-module
import shutil
import requests
from copr_common.enums import StorageEnum
from copr_backend.helpers import call_copr_repo, build_chroot_log_name, ensure_dir_exists
from copr_backend.pulp import PulpClient
from copr_backend.exceptions import CoprBackendError
from .sign import resign_rpms_in_dir


def storage_for_job(job, opts, log):
    """
    Return an appropriate storage object for a given job
    """
    # pylint: disable=too-many-function-args
    return storage_for_enum(
        job.storage,
        job.project_owner,
        job.project_name,
        job.appstream,
        job.uses_devel_repo,
        opts,
        log,
    )


def storage_for_enum(enum_value, owner, project, appstream, devel, opts, log):
    """
    Return an appropriate `StorageEnum` value
    """
    args = [owner, project, appstream, devel, opts, log]
    if enum_value == StorageEnum.pulp:
        return PulpStorage(*args)
    return BackendStorage(*args)


class Storage:
    """
    Storage agnostic, high-level interface for storing and acessing our data
    """

    def __init__(self, owner, project, appstream, devel, opts, log):
        self.owner = owner
        self.project = project
        self.appstream = appstream
        self.devel = devel
        self.opts = opts
        self.log = log

    def init_project(self, dirname, chroot):
        """
        Make sure users can enable a DNF repository for this project/chroot

        This function is called in various situations.
        Some of them you might not expect:

        1. A new project is created
        2. User clicks the "Regenerate" button in project overview
        3. The "manual createrepo" feature is toggled for the project
        4. A chroot is enabled for the project
        """
        raise NotImplementedError

    def upload_build_results(self, chroot, results_dir, target_dir_name, max_workers=1, build_id=None):
        """
        Add results for a new build to the storage
        """

    def publish_repository(self, chroot, **kwargs):
        """
        Publish new build results in the repository

        See when we run createrepo
        https://docs.pagure.org/copr.copr/createrepo.html
        """
        raise NotImplementedError

    def delete_repository(self, chroot):
        """
        Delete a repository and all of its builds
        """
        raise NotImplementedError

    def delete_project(self, dirname):
        """
        Delete the whole project and all of its repositories and builds
        """
        raise NotImplementedError

    def delete_builds(self, dirname, chroot_builddirs, build_ids):
        """
        Delete multiple builds from the storage
        """
        raise NotImplementedError

    def repository_exists(self, dirname, chroot, baseurl):
        """
        Does a repository exist?
        """
        raise NotImplementedError

    def fork_project(self, src_fullname, dst_fullname, builds_map):
        """
        Fork build results from one project to another
        """


class BackendStorage(Storage):
    """
    Store build results in `/var/lib/copr/public_html/results/`
    """

    def init_project(self, dirname, chroot):
        self.log.info("Creating repo for: %s/%s/%s",
                      self.owner, dirname, chroot)
        repo = os.path.join(self.opts.destdir, self.owner,
                            dirname, chroot)
        try:
            os.makedirs(repo)
            self.log.info("Empty repo so far, directory created")
        except FileExistsError:
            pass

        return call_copr_repo(repo, appstream=self.appstream, devel=self.devel,
                              logger=self.log)

    def publish_repository(self, chroot, **kwargs):
        assert "chroot_dir" in kwargs
        assert "target_dir_name" in kwargs

        base_url = "/".join([self.opts.results_baseurl, self.owner,
                             self.project, chroot])

        self.log.info("Incremental createrepo run, adding %s into %s, "
                      "(auto-create-repo=%s)", kwargs["target_dir_name"],
                      base_url, not self.devel)
        return call_copr_repo(kwargs["chroot_dir"], devel=self.devel,
                              add=[kwargs["target_dir_name"]],
                              logger=self.log,
                              appstream=self.appstream)

    def delete_repository(self, chroot):
        chroot_path = os.path.join(
            self.opts.destdir, self.owner, self.project, chroot)

        self.log.info("Going to delete: %s", chroot_path)
        if not os.path.isdir(chroot_path):
            self.log.error("Directory %s not found", chroot_path)
            return
        shutil.rmtree(chroot_path)

    def delete_project(self, dirname):
        path = os.path.join(self.opts.destdir, self.owner, dirname)
        if os.path.exists(path):
            self.log.info("Removing copr dir %s", path)
            shutil.rmtree(path)

    def delete_builds(self, dirname, chroot_builddirs, build_ids):
        result = True
        for chroot, subdirs in chroot_builddirs.items():
            chroot_path = os.path.join(
                self.opts.destdir, self.owner, dirname, chroot)
            if not os.path.exists(chroot_path):
                self.log.error("%s chroot path doesn't exist", chroot_path)
                result = False
                continue

            self.log.info("Deleting subdirs [%s] in %s",
                          ", ".join(subdirs), chroot_path)

            # Run createrepo first and then remove the files (to avoid old
            # repodata temporarily pointing at non-existing files)!
            # In srpm-builds we don't create repodata at all
            if chroot != "srpm-builds":
                repo = call_copr_repo(
                    chroot_path, delete=subdirs, devel=self.devel,
                    appstream=self.appstream, logger=self.log)
                if not repo:
                    result = False

            for build_id in build_ids or []:
                log_paths = [
                    os.path.join(chroot_path, build_chroot_log_name(build_id)),
                    # we used to create those before
                    os.path.join(chroot_path, 'build-{}.rsync.log'.format(build_id)),
                    os.path.join(chroot_path, 'build-{}.log'.format(build_id))]
                for log_path in log_paths:
                    try:
                        os.unlink(log_path)
                    except OSError:
                        self.log.debug("can't remove %s", log_path)
        return result

    def repository_exists(self, dirname, chroot, baseurl):
        repodata = os.path.join(self.opts.destdir, self.owner, dirname,
                                chroot, "repodata", "repomd.xml")
        return os.path.exists(repodata)

    def fork_project(self, src_fullname, dst_fullname, builds_map):
        dst_owner, dst_project = dst_fullname.split("/")
        old_path = os.path.join(self.opts.destdir, src_fullname)
        new_path = os.path.join(self.opts.destdir, dst_fullname)

        if not os.path.exists(old_path):
            self.log.info("Source copr directory doesn't exist: %s", old_path)
            return False

        chroot_paths = set()
        for chroot, src_dst_dir in builds_map.items():
            if not chroot or not src_dst_dir:
                continue

            for old_dir_name, new_dir_name in src_dst_dir.items():
                src_dir, dst_dir = old_dir_name, new_dir_name

                if not src_dir or not dst_dir:
                    continue

                new_chroot_path = self._fork_build(
                    chroot,
                    old_path,
                    new_path,
                    src_dir,
                    dst_dir,
                    dst_owner,
                    dst_project,
                )
                if new_chroot_path and chroot != "srpm-builds":
                    chroot_paths.add(new_chroot_path)

        for chroot_path in chroot_paths:
            if not call_copr_repo(chroot_path, logger=self.log):
                return False
        return True

    def _fork_build(self, chroot, old_path, new_path, src_dir, dst_dir, dst_owner, dst_project):
        # pylint: disable=too-many-positional-arguments
        old_chroot_path = os.path.join(old_path, chroot)
        new_chroot_path = os.path.join(new_path, chroot)

        src_path = os.path.join(old_chroot_path, src_dir)
        dst_path = os.path.join(new_chroot_path, dst_dir)

        ensure_dir_exists(dst_path, self.log)

        try:
            copy_tree(src_path, dst_path)
        except DistutilsFileError as e:
            self.log.error(str(e))
            return None

        resign_rpms_in_dir(dst_owner, dst_project, dst_path, chroot, self.opts, self.log)

        self.log.info("Forked build %s as %s", src_path, dst_path)
        return new_chroot_path


class PulpStorage(Storage):
    """
    Store build results in Pulp
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = PulpClient.create_from_config_file(log=self.log, opts=self.opts)

    def init_project(self, dirname, chroot):
        repository_name = self._repository_name(chroot, dirname)
        response = self.client.create_repository(repository_name)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp repository %s because of %s",
                           repository_name, response.text)
            return False

        # When a repository is mentioned in other endpoints, it needs to be
        # mentioned by its href, not name
        response = self.client.get_repository(repository_name)
        repository = response.json()["results"][0]
        repository_href = repository["pulp_href"]

        distribution_name = self._distribution_name(chroot, dirname)
        public_distribution_name = self._distribution_name(chroot, dirname, devel=False)
        devel_distribution_name = self._distribution_name(chroot, dirname, devel=True)

        response = self.client.create_distribution(distribution_name, repository_href)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp distribution %s because of %s",
                           public_distribution_name, response.text)
            return False

        # If a project enabled the manual createrepo mode, we need to create a
        # devel distribution to be consumed by other builds within the project
        if self.devel:
            # Wait until we can get the publication
            if task := response.json().get("task"):
                self.client.wait_for_finished_task(task)
            response = self.client.get_publication(repository_href)
            publication = response.json()["results"][0]["pulp_href"]
            public_distribution = self._get_distribution(chroot, dirname, devel=False)

            response = self.client.update_distribution(public_distribution, publication=publication)
            if not response.ok:
                self.log.error("Failed to update Pulp distribution %s for because %s",
                               public_distribution, response.text)

        # This means a project is being created. We do nothing.
        elif repository["latest_version_href"].endswith("/versions/0/"):
            pass

        # The following happens in multiple situations:
        # 1. The "Regenerate" button was clicked for a manual createrepo
        #    project. Then we want to copy packages from the devel repo to the
        #    public repo. Or more precisely, point the public distribution to
        #    the same publication as the devel distribution points to.
        # 2. A project disabled the manual createrepo feature. Then we want to
        #    do the same as the "Regenerate" button above.
        #
        # A note regarding implementation:
        # It is weird to do this in the `init_project` method, pointing to the
        # fact that our abstractions are probably wrong and should be fixed.
        # We have the `publish_repository` method which is called after a build
        # is finished. We don't want to copy the packages there. This
        # `init_project` method is called when a project is created (for which
        # the copying does nothing) but also when a "Regenerate" button is
        # clicked (for which we copy the data). We should probably separate
        # these two concepts.
        else:
            response = self.client.get_publication(repository_href)
            publication = response.json()["results"][0]["pulp_href"]

            self.log.info(
                "Pointing %s to the same publication as %s which is %s",
                public_distribution_name,
                devel_distribution_name,
                publication,
            )
            public_distribution = self._get_distribution(chroot)
            response = self.client.update_distribution(public_distribution, publication=publication)
            if not response.ok:
                self.log.error("Failed to update Pulp distribution %s for because %s",
                               public_distribution_name, response.text)
                return False

        # And finally, run the actual createrepo for either the devel or
        # the public repository
        response = self.client.create_publication(repository_href)
        return response.ok

    def upload_rpm(self, path, labels):
        """
        Add an RPM to the storage
        """
        response = self.client.create_content(path, labels)

        if not response.ok:
            self.log.error("Failed to create Pulp content for: %s, %s",
                           path, response.text)
            return response

        return response

    def upload_build_results(self, chroot, results_dir, target_dir_name, max_workers=1, build_id=None):
        futures = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for root, _, files in os.walk(results_dir):
                for name in files:
                    if os.path.basename(root) == "prev_build_backup":
                        continue

                    # TODO Should all results (logs, configs, fedora-review results)
                    # be added to Pulp, or only RPM packages?
                    # `pulp rpm content create ...` cannot be executed on text files
                    # and fails with `RPM file cannot be parsed for metadata`
                    if not name.endswith(".rpm"):
                        continue

                    path = os.path.join(root, name)
                    labels = {"build_id": build_id, "chroot": chroot}
                    futures[executor.submit(self.upload_rpm, path, labels)] = name

            failed_uploads = []
            exceptions = []
            package_hrefs = []
            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    response = future.result()
                    if response.ok:
                        created = response.json().get("pulp_href")
                        package_hrefs.append(created)
                        self.log.info("Uploaded to Pulp: %s", filepath)
                    else:
                        failed_uploads.append(filepath)
                except RuntimeError as exc:
                    exceptions.append(f"{filepath} generated an exception: {exc}")

            if failed_uploads:
                raise CoprBackendError(
                    "Pulp uploads of  {0} failed.".format(failed_uploads))
            if exceptions:
                raise CoprBackendError(f"Exceptions encountered: {exceptions}")

            return package_hrefs

    def create_repository_version(self, dirname, chroot, package_hrefs):
        """
        Create a new repository version by adding a list of RPMs to the latest repository version.
        """
        repository = self._get_repository(chroot, dirname)
        return self.client.add_content(repository, package_hrefs)

    def publish_repository(self, chroot, **kwargs):
        # Publishing occurs after each repository version is created.
        return True

    def delete_repository(self, chroot):
        repository = self._get_repository(chroot)
        distribution = self._get_distribution(chroot)
        self.client.delete_repository(repository)
        self.client.delete_distribution(distribution)

    def delete_project(self, dirname):
        prefix = "{0}/{1}".format(self.owner, dirname)
        response = self.client.list_distributions(prefix)
        distributions = response.json()["results"]
        for distribution in distributions:
            self.client.delete_distribution(distribution["pulp_href"])
            if distribution["repository"]:
                self.client.delete_repository(distribution["repository"])

    def delete_builds(self, dirname, chroot_builddirs, build_ids):
        # pylint: disable=too-many-locals
        result = True
        for chroot, subdirs in chroot_builddirs.items():
            # We don't upload results of source builds to Pulp
            if chroot == "srpm-builds":
                continue

            chroot_path = os.path.join(
                self.opts.destdir, self.owner, dirname, chroot)
            if not os.path.exists(chroot_path):
                self.log.error("%s chroot path doesn't exist", chroot_path)
                result = False
                continue

            repository = self._get_repository(chroot)
            # Find the RPMs by list of build ids
            content_response = self.client.get_content(build_ids)
            list_of_prns = [package["prn"] for package in content_response.json()["results"] ]
            self.client.delete_content(repository, list_of_prns)
            self.log.info("Deleted resources: %s", list_of_prns)

            # Delete results from the backend (logs, info files, etc)
            for subdir in subdirs:
                path = os.path.join(chroot_path, subdir)
                shutil.rmtree(path)
        return result

    def repository_exists(self, dirname, chroot, baseurl):
        repodata = "{0}/repodata/repomd.xml".format(baseurl)
        response = requests.head(repodata)
        return response.ok

    def fork_project(self, src_fullname, dst_fullname, builds_map):
        _dst_owner, dst_project = dst_fullname.split("/")
        for chroot, src_dst_dir in builds_map.items():
            if not chroot or not src_dst_dir:
                continue

            # It should be a dirname here but since forking CoprDirs is not
            # supported yet, we pass the project name
            # See https://github.com/fedora-copr/copr/issues/3820
            if not self.init_project(dst_project, chroot):
                self.log.error("Failed to init the dst project")
                return False

            for old_dir_name, new_dir_name in src_dst_dir.items():
                src_dir, dst_dir = old_dir_name, new_dir_name
                if not src_dir or not dst_dir:
                    continue

                src_build_id = int(src_dir.split("-")[0])
                dst_build_id = int(dst_dir.split("-")[0])

                # Forking doesn't support CoprDirs yet. For now, let's assume
                # all builds are in the main CoprDir.
                # See https://github.com/fedora-copr/copr/issues/3820
                dst_dirname = dst_fullname.split("/")[1]

                self._fork_build(
                    src_build_id,
                    dst_build_id,
                    src_fullname.split("/")[0],
                    src_fullname.split("/")[1],
                    dst_fullname.split("/")[0],
                    dst_fullname.split("/")[1],
                    dst_dirname,
                    chroot,
                )

            repository = self._get_repository(chroot)
            if not self.client.create_publication(repository):
                self.log.error("Failed to publish a repository")
                return False

        return True

    def _fork_build(self, src_build_id, dst_build_id, src_owner, src_project,
                    dst_owner, dst_project, dst_dirname, chroot):
        # pylint: disable=too-many-positional-arguments
        src_fullname = "{0}/{1}".format(src_owner, src_project)
        with TemporaryDirectory(prefix="copr-fork-") as tmp:
            response = self.client.get_content([src_build_id], chroot)
            rpms = response.json()["results"]
            for rpm in rpms:
                filename = rpm["location_href"]
                url = "{0}/{1}/{2}/Packages/{3}/{4}".format(
                    self.opts.pulp_content_url,
                    src_fullname,
                    chroot,
                    filename[0],
                    filename,
                )

                self.log.info("Downloading %s", url)
                response = requests.get(url, timeout=60)

                # The package was likely in a CoprDir and forking supports only
                # main CoprDirs now. This check could be improved though.
                if response.status_code == 404:
                    self.log.error("Not found %s", url)
                    continue

                if not response.ok:
                    self.log.error("Failed to download %s because %s",
                                   url, response.reason)
                    return False

                path = os.path.join(tmp, os.path.basename(url))
                with open(path, "wb") as fp:
                    fp.write(response.content)

            # It is possible we didn't download any RPMs. That would be the case
            # for builds in CoprDirs.
            if not os.listdir(tmp):
                return None

            resign_rpms_in_dir(
                dst_owner,
                dst_project,
                tmp,
                chroot,
                self.opts,
                self.log,
            )
            result = self.upload_build_results(
                chroot,
                tmp,
                None,  # This atribute is only relevant for the backend storage
                build_id=dst_build_id,
            )

        self.log.info("Forked Pulp build %s as %s", src_build_id, dst_build_id)
        return self.create_repository_version(dst_dirname, chroot, result)

    def _repository_name(self, chroot, dirname=None):
        return "/".join([
            self.owner,
            dirname or self.project,
            chroot,
        ])

    def _distribution_name(self, chroot, dirname=None, devel=None):
        # On backend we use /devel but in Pulp we cannot create subdirectories
        repository = self._repository_name(chroot, dirname)
        if devel is None:
            devel = self.devel
        if devel:
            return "{0}-devel".format(repository)
        return repository

    def _get_repository(self, chroot, dirname=None):
        name = self._repository_name(chroot, dirname)
        response = self.client.get_repository(name)
        return response.json()["results"][0]["pulp_href"]

    def _get_distribution(self, chroot, dirname=None, devel=None):
        if devel is None:
            devel = self.devel
        name = self._distribution_name(chroot, dirname, devel=devel)
        response = self.client.get_distribution(name)
        return response.json()["results"][0]["pulp_href"]
