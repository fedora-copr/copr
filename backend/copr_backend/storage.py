"""
Support for various data storages, e.g. results directory on backend, Pulp, etc.
"""

import os
from copr_backend.helpers import call_copr_repo
from copr_backend.helpers import run_cmd


def storage_for_task(task, opts, log):
    """
    Return an appropriate storage object for a given task (build or action)
    """
    if task.get("pulp"):
        return PulpStorage(opts, log)
    return BackendStorage(opts, log)


class Storage:
    """
    Storage agnostic, high-level interface for storing and acessing our data
    """

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def createrepo(self, ownername, coprdir, chroot, appstream, devel):
        """
        Ensure that a results directory for a given project exists and run
        createrepo_c in it
        """
        raise NotImplementedError


class BackendStorage(Storage):
    """
    Store build results in `/var/lib/copr/public_html/results/`
    """

    def createrepo(self, ownername, coprdir, chroot, appstream, devel):
        self.log.info("Creating repo for: %s/%s/%s",
                      ownername, coprdir, chroot)
        repo = os.path.join(self.opts.destdir, ownername,
                            coprdir, chroot)
        try:
            os.makedirs(repo)
            self.log.info("Empty repo so far, directory created")
        except FileExistsError:
            pass

        return call_copr_repo(repo, appstream=appstream, devel=devel,
                              logger=self.log)


class PulpStorage(Storage):
    """
    Store build results in Pulp
    """

    def createrepo(self, ownername, coprdir, chroot, appstream, devel):
        repository = "/".join([ownername, coprdir, chroot])
        result = self._create_repository(repository)
        if result.returncode and "This field must be unique" not in result.stderr:
            self.log.error("Failed to create a Pulp repository %s because of %s",
                           repository, result.stderr)
            return False

        distribution = "{0}-devel".format(repository) if devel else repository
        result = self._create_distribution(distribution, repository)
        if result.returncode and "This field must be unique" not in result.stderr:
            self.log.error("Failed to create a Pulp distribution %s because of %s",
                           distribution, result.stderr)
            return False

        result = self._create_publication(repository)
        return result.returncode == 0

    def _create_repository(self, name):
        return run_cmd([
            "/usr/bin/pulp", "rpm", "repository", "create",
            "--name", name,
        ])

    def _create_distribution(self, name, repository, basepath=None):
        return run_cmd([
            "/usr/bin/pulp", "rpm", "distribution", "create",
            "--name", name,
            "--repository", repository,
            "--base-path", basepath or name,
        ])

    def _create_publication(self, repository):
        return run_cmd([
            "/usr/bin/pulp", "rpm", "publication", "create",
            "--repository", repository,
        ])
