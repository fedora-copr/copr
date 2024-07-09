"""
Support for various data storages, e.g. results directory on backend, Pulp, etc.
"""

import os
import json
import shutil
from copr_common.enums import StorageEnum
from copr_backend.helpers import call_copr_repo, build_chroot_log_name
from copr_backend.pulp import PulpClient


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
        """
        raise NotImplementedError

    def upload_build_results(self, chroot, results_dir, target_dir_name):
        """
        Add results for a new build to the storage
        """

    def publish_repository(self, chroot, **kwargs):
        """
        Publish new build results in the repository
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


class PulpStorage(Storage):
    """
    Store build results in Pulp
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = PulpClient.create_from_config_file()

    def init_project(self, dirname, chroot):
        repository = self._repository_name(chroot)
        response = self.client.create_repository(repository)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp repository %s because of %s",
                           repository, response.text)
            return False

        # When a repository is mentioned in other endpoints, it needs to be
        # mentioned by its href, not name
        repository = self._get_repository(chroot)

        distribution = self._distribution_name(chroot)
        response = self.client.create_distribution(distribution, repository)
        if not response.ok and "This field must be unique" not in response.text:
            self.log.error("Failed to create a Pulp distribution %s because of %s",
                           distribution, response.text)
            return False

        response = self.client.create_publication(repository)
        return response.ok

    def upload_build_results(self, chroot, results_dir, target_dir_name):
        artifacts = []
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
                response = self.client.upload_artifact(path)
                if not response.ok:
                    self.log.error("Failed to upload %s to Pulp", path)
                    continue

                artifact = response.json()["pulp_href"]
                artifacts.append(artifact)
                relative_path = os.path.join(
                    self.owner, self.project, target_dir_name)

                repository = self._get_repository(chroot)
                response = self.client.create_content(repository, path)

                if not response.ok:
                    self.log.error("Failed to create Pulp content for: %s, %s",
                                   path, response.text)
                    continue

                self.log.info("Uploaded to Pulp: %s", path)

        data = {"artifacts": artifacts}
        path = os.path.join(results_dir, "pulp.json")
        with open(path, "w+", encoding="utf8") as fp:
            json.dump(data, fp)

    def publish_repository(self, chroot, **kwargs):
        repository = self._get_repository(chroot)
        response = self.client.create_publication(repository)
        if not response.ok:
            self.log.error("Failed to create Pulp publication for because %s",
                           repository, response.text)
            return False

        task = response.json()["task"]
        response = self.client.get_task(task)
        if not response.ok:
            self.log.error("Failed to get Pulp task %s because of %s",
                           task, response.text)
            return False

        publication = response.json()["created_resources"][0]
        distribution_name = self._distribution_name(chroot)
        distribution = self._get_distribution(chroot)

        # Do we want to update the distribution to point to a specific
        # publication? When not doing so, the distribution should probably
        # automatically point to the latest publication
        response = self.client.update_distribution(distribution, publication)
        if not response.ok:
            self.log.error("Failed to update Pulp distribution %s for because %s",
                           distribution_name, response.text)
            return False
        return True

    def delete_repository(self, chroot):
        repository = self._get_repository(chroot)
        distribution = self._get_distribution(chroot)
        self.client.delete_repository(repository)
        self.client.delete_distribution(distribution)

    def delete_project(self, dirname):
        prefix = "{0}/{1}".format(self.owner, dirname)
        response = self.client.list_repositories(prefix)
        repositories = response.json()["results"]
        for repository in repositories:
            self.client.delete_repository(repository["pulp_href"])

    def delete_builds(self, dirname, chroot_builddirs, build_ids):
        # pylint: disable=too-many-locals
        result = True
        for chroot, subdirs in chroot_builddirs.items():
            if chroot == "srpm-builds":
                continue

            chroot_path = os.path.join(
                self.opts.destdir, self.owner, dirname, chroot)
            if not os.path.exists(chroot_path):
                self.log.error("%s chroot path doesn't exist", chroot_path)
                result = False
                continue

            repository = self._get_repository(chroot)
            reponame = self._repository_name(chroot, dirname=dirname)
            repoversion = self.client.get_latest_repository_version(reponame)

            # It is currently not possible to set labels for Pulp content.
            # https://github.com/pulp/pulpcore/issues/3338
            # Until it is implemented, we need to query all packages from a
            # given repository(version) and manually filter only the artifacts
            # for this build ID. Which we know from pulp.json in the resultdir.
            packages = self.client.list_packages(repoversion).json()["results"]
            a2c = {x["artifact"]: x["pulp_href"] for x in packages}

            for subdir in subdirs:
                path = os.path.join(chroot_path, subdir, "pulp.json")
                with open(path, "r", encoding="utf8") as fp:
                    pulp = json.load(fp)

                for artifact in pulp["artifacts"]:
                    content = a2c.get(artifact)
                    if not content:
                        msg = "Pulp content for artifact %s doesn't exist, skipping."
                        self.log.info(msg, artifact)
                        continue

                    response = self.client.delete_content(repository, [content])
                    if response.ok:
                        self.log.info("Successfully deleted Pulp content %s", content)
                    else:
                        result = False
                        self.log.info("Failed to delete Pulp content %s", content)

        return result

    def _repository_name(self, chroot, dirname=None):
        return "/".join([
            self.owner,
            dirname or self.project,
            chroot,
        ])

    def _distribution_name(self, chroot):
        repository = self._repository_name(chroot)
        if self.devel:
            return "{0}-devel".format(repository)
        return repository

    def _get_repository(self, chroot):
        name = self._repository_name(chroot)
        response = self.client.get_repository(name)
        return response.json()["results"][0]["pulp_href"]

    def _get_distribution(self, chroot):
        name = self._distribution_name(chroot)
        response = self.client.get_distribution(name)
        return response.json()["results"][0]["pulp_href"]
