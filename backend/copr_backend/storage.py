"""
Support for various data storages, e.g. results directory on backend, Pulp, etc.
"""

import os
from copr_common.enums import StorageEnum
from copr_backend.helpers import call_copr_repo
from copr_backend.pulp import PulpClient


def storage_for_job(job, opts, log):
    """
    Return an appropriate storage object for a given job
    """
    return storage_for_enum(job.storage, opts, log)


def storage_for_enum(enum_value, opts, log):
    """
    Return an appropriate `StorageEnum` value
    """
    if enum_value == StorageEnum.pulp:
        return PulpStorage(opts, log)
    return BackendStorage(opts, log)


class Storage:
    """
    Storage agnostic, high-level interface for storing and acessing our data
    """

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def init_project(self, job):
        """
        Make sure users can enable a DNF repository for this project/chroot
        """
        raise NotImplementedError

    def upload_build_results(self, job):
        """
        Add results for a new build to the storage
        """

    def publish_repository(self, job):
        """
        Publish new build results in the repository
        """
        raise NotImplementedError


class BackendStorage(Storage):
    """
    Store build results in `/var/lib/copr/public_html/results/`
    """

    def init_project(self, job):
        ownername = job.project_owner
        coprdir = job.project_name
        chroot = job.chroot

        self.log.info("Creating repo for: %s/%s/%s",
                      ownername, coprdir, chroot)
        repo = os.path.join(self.opts.destdir, ownername,
                            coprdir, chroot)
        try:
            os.makedirs(repo)
            self.log.info("Empty repo so far, directory created")
        except FileExistsError:
            pass

        return call_copr_repo(repo, appstream=job.appstream, devel=job.devel,
                              logger=self.log)

    def publish_repository(self, job):
        project_owner = job.project_owner
        project_name = job.project_name
        devel = job.uses_devel_repo
        appstream = job.appstream

        base_url = "/".join([self.opts.results_baseurl, project_owner,
                             project_name, job.chroot])

        self.log.info("Incremental createrepo run, adding %s into %s, "
                      "(auto-create-repo=%s)", job.target_dir_name,
                      base_url, not devel)
        return call_copr_repo(job.chroot_dir, devel=devel,
                              add=[job.target_dir_name],
                              logger=self.log,
                              appstream=appstream)


class PulpStorage(Storage):
    """
    Store build results in Pulp
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = PulpClient.create_from_config_file()

    def init_project(self, job):
        repository = self._repository_name(job)
        response = self.client.create_repository(repository)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp repository %s because of %s",
                           repository, response.text)
            return False

        # When a repository is mentioned in other endpoints, it needs to be
        # mentioned by its href, not name
        repository = self._get_repository(job)

        distribution = self._distribution_name(job)
        response = self.client.create_distribution(distribution, repository)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp distribution %s because of %s",
                           distribution, response.text)
            return False

        response = self.client.create_publication(repository)
        return response.ok

    def upload_build_results(self, job):
        for root, _, files in os.walk(job.results_dir):
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
                response = self.client.upload_artifact(path)
                if not response.ok:
                    self.log.error("Failed to upload %s to Pulp", path)
                    continue

                artifact = response.json()["pulp_href"]
                relative_path = os.path.join(
                    job.project_owner, job.project_name, job.target_dir_name)

                repository = self._get_repository(job)
                response = self.client.create_content(
                    repository, artifact, relative_path)

                if not response.ok:
                    self.log.error("Failed to create Pulp content for: %s, %s",
                                   path, response.text)
                    continue

                self.log.info("Uploaded to Pulp: %s", path)

    def publish_repository(self, job):
        repository = self._get_repository(job)
        response = self.client.create_publication(repository)
        if not response.ok:
            self.log.error("Failed to create Pulp publication for because %s",
                           repository, response.text)
            return False

        publication = response.json()["results"][0]["pulp_href"]
        distribution_name = self._distribution_name(job)
        distribution = self._get_distribution(job)

        # Do we want to update the distribution to point to a specific
        # publication? When not doing so, the distribution should probably
        # automatically point to the latest publication
        response = self.client.update_distribution(distribution, publication)
        if not response.ok:
            self.log.error("Failed to update Pulp distribution %s for because %s",
                           distribution_name, response.text)
            return False
        return True

    def _repository_name(self, job):
        return "/".join([
            job.project_owner,
            job.project_name,
            job.chroot,
        ])

    def _distribution_name(self, job):
        repository = self._repository_name(job)
        if job.uses_devel_repo:
            return "{0}-devel".format(repository)
        return repository

    def _get_repository(self, job):
        name = self._repository_name(job)
        response = self.client.get_repository(name)
        return response.json()["results"][0]["pulp_href"]

    def _get_distribution(self, job):
        name = self._distribution_name(job)
        response = self.client.get_distribution(name)
        return response.json()["results"][0]["pulp_href"]
