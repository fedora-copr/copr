"""
Pulp doesn't provide an API client, we are implementing it for ourselves
"""

import json
import logging
import os
import time
import tomllib
from urllib.parse import urlencode
import requests

from copr_common.lock import lock, LockTimeout
from copr_common.redis_helpers import get_redis_connection


class BatchedAddRemoveContent:
    """
    Group a set of `add_and_remove` tasks for a single Pulp repository.
    """
    def __init__(self, repo_href, rpms_to_add, rpms_to_remove, backend_opts=None, log=None, noop=False):
        self.repo_href = repo_href
        self.rpms_to_add = rpms_to_add or []
        self.rpms_to_remove = rpms_to_remove or []
        self.log = log
        self.noop = noop

        if not backend_opts:
            self.log.error("can't get access to redis, batch disabled")
            self.noop = True
            return

        self._pid = os.getpid()
        self._json_redis_task = json.dumps({
            "add_content_units": self.rpms_to_add,
            "remove_content_units": self.rpms_to_remove,
        })

        self.notify_keys = []
        self.redis = get_redis_connection(backend_opts)

    @property
    def key(self):
        """ Our instance ID (key in Redis DB) """
        return "add_remove_batched::{}::{}".format(
            self.repo_href, self._pid)

    @property
    def key_pattern(self):
        """ Redis key pattern for potential tasks we can batch-process """
        return "add_remove_batched::{}::*".format(self.repo_href)

    def make_request(self):
        """ Request the task into Redis DB.  Run _before_ lock! """
        if self.noop:
            return None
        self.redis.hset(self.key, "task", self._json_redis_task)
        return self.key

    def check_processed(self, delete_if_not=True):
        """
        Drop our entry from Redis DB (if any), and return True if the task is
        already processed.  When 'delete_if_not=True, we delete the self.key
        from Redis even if the task is not yet processed (meaning that caller
        plans to finish the task right away).
        """
        if self.noop:
            return False

        status = self.redis.hget(self.key, "status") == "success"
        self.log.debug("Has already a status? %s", status)

        try:
            if not status:
                # not yet processed
                return False
        finally:
            # This is atomic operation, other processes may not re-start doing this
            # task again.  https://github.com/redis/redis/issues/9531
            #
            # The 'delete_if_not = True' is not a TOCTOU case.  Our caller holds
            # the lock, hence no other machine may take our task (would require
            # lock) and re-process it.
            if status or delete_if_not:
                self.redis.delete(self.key)

        return status

    def options(self):
        """
        Get the options from other _compatible_ (see below) Redis tasks, and
        plan the list of tasks in self.notify_keys[] that we will notify in
        commit().
        """
        rpms_to_add = set(self.rpms_to_add)
        rpms_to_remove = set(self.rpms_to_remove)

        if self.noop:
            return {"add_content_units": rpms_to_add, "remove_content_units": rpms_to_remove}

        for key in self.redis.keys(self.key_pattern):
            assert key != self.key

            task_dict = self.redis.hgetall(key)
            if not task_dict:
                # TOCTOU: The key might no longer exist in DB, even though
                # _our process_ holds the lock!  See the
                # 'self.redis.delete(self.key)' above in check_processed(); the
                # _original process_ removes key without locking, if _third_
                # process commit()ted the status=succeeded.
                # Prior fixing #3770/#3777 we tried to process these deleted
                # tasks and ended up with KeyError on task_dict["task"] below.
                self.log.info("Key %s already processed (by other process), "
                              "removed by the original process (without lock) "
                              "since we listed it.", key)
                continue

            if task_dict.get("status") is not None:
                # skip processed tasks
                self.log.info("Key %s already processed, skip", key)
                continue

            task_opts = json.loads(task_dict["task"])

            # we can process this task!
            self.notify_keys.append(key)

            # append "add" tasks, if that makes sense
            rpms_to_add.update(task_opts["add_content_units"])
            rpms_to_remove.update(task_opts["remove_content_units"])

        # Make sure we are not adding and removing the same packages
        common = rpms_to_add & rpms_to_remove
        rpms_to_add -= common
        rpms_to_remove -= common

        return {"add_content_units": list(rpms_to_add), "remove_content_units": list(rpms_to_remove)}

    def commit(self):
        """
        Report that we processed other createrepo requests.  We don't report
        about failures, we rather kindly let the responsible processes to re-try
        the createrepo tasks.  Requires lock!
        """
        if self.noop:
            return

        for key in self.notify_keys:
            self.log.info("Notifying %s that we succeeded", key)
            self.redis.hset(key, "status", "success")


class PulpClient:
    """
    A client for interacting with Pulp API.

    API documentation:
    - https://docs.pulpproject.org/pulp_rpm/restapi.html
    - https://docs.pulpproject.org/pulpcore/restapi.html

    A note regarding PUT vs PATCH:
    - PUT changes all data and therefore all required fields needs to be sent
    - PATCH changes only the data that we are sending

    A lot of the methods require repository, distribution, publication, etc,
    to be the full API endpoint (called "pulp_href"), not simply their name.
    If method argument doesn't have "name" in its name, assume it expects
    pulp_href. It looks like this:
    /pulp/api/v3/publications/rpm/rpm/5e6827db-260f-4a0f-8e22-7f17d6a2b5cc/
    """

    @classmethod
    def create_from_config_file(cls, path=None, log=None, opts=None):
        """
        Create a Pulp client from a standard configuration file that is
        used by the `pulp` CLI tool
        """
        path = os.path.expanduser(path or "~/.config/pulp/cli.toml")
        with open(path, "rb") as fp:
            config = tomllib.load(fp)
        return cls(config["cli"], log, opts)

    def __init__(self, config, log=None, opts=None):
        self.config = config
        self.timeout = 60
        self.log = log or logging.getLogger(__name__)
        self.opts = opts

    @property
    def auth(self):
        """
        https://requests.readthedocs.io/en/latest/user/authentication/
        """
        return (self.config["username"], self.config["password"])

    @property
    def cert(self):
        """
        See Client Side Certificates
        https://docs.python-requests.org/en/latest/user/advanced/
        """
        return (self.config["cert"], self.config["key"])

    def url(self, endpoint):
        """
        A fully qualified URL for a given API endpoint
        """
        domain = self.config["domain"]
        if domain == "default":
            domain = ""

        relative = os.path.normpath("/".join([
            self.config["api_root"],
            domain,
            endpoint,
        ]))

        # Normpath removes the trailing slash. If it was there, put it back
        if endpoint[-1] == "/":
            relative += "/"
        return self.config["base_url"] + relative

    @property
    def request_params(self):
        """
        Default parameters for our requests
        """
        params = {"timeout": self.timeout}
        if all(self.cert):
            params["cert"] = self.cert
        else:
            params["auth"] = self.auth
        return params

    def create_repository(self, name):
        """
        Create an RPM repository
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_create
        """
        uri = "/api/v3/repositories/rpm/rpm/"
        data = {"name": name, "retain_repo_versions": 1, "retain_package_versions": 5}
        self.log.info("Pulp: create_repository: %s %s", uri, name)
        return requests.post(self.url(uri), json=data, **self.request_params)

    def get_repository(self, name):
        """
        Get a single RPM repository
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_list
        """
        # There is no endpoint for querying a single repository by its name,
        # even Pulp CLI does this workaround
        uri = "/api/v3/repositories/rpm/rpm/?"
        uri += urlencode({"name": name, "offset": 0, "limit": 1})
        self.log.info("Pulp: get_repository: %s", uri)
        return requests.get(self.url(uri), **self.request_params)

    def get_distribution(self, name):
        """
        Get a single RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_list
        """
        # There is no endpoint for querying a single repository by its name,
        # even Pulp CLI does this workaround
        uri = "/api/v3/distributions/rpm/rpm/?"
        uri += urlencode({"name": name, "offset": 0, "limit": 1})
        self.log.info("Pulp: get_distribution: %s", uri)
        return requests.get(self.url(uri), **self.request_params)

    def get_task(self, task):
        """
        Get a detailed information about a task
        """
        return self.get_by_href(task)

    def get_by_href(self, href):
        """
        Get a detailed information about an object
        """
        url = self.config["base_url"] + href
        self.log.info("Pulp: get_by_href: %s", href)
        return requests.get(url, **self.request_params)

    def create_distribution(self, name, repository, basepath=None):
        """
        Create an RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_create
        """
        uri = "/api/v3/distributions/rpm/rpm/"
        data = {
            "name": name,
            "repository": repository,
            "base_path": basepath or name,
        }
        self.log.info("Pulp: create_distribution: %s %s %s", uri, data)
        return requests.post(self.url(uri), json=data, **self.request_params)

    def create_publication(self, repository):
        """
        Create an RPM publication
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Publications:-Rpm/operation/publications_rpm_rpm_create
        """
        uri = "/api/v3/publications/rpm/rpm/"
        data = {"repository": repository}
        self.log.info("Pulp: publishing %s %s", uri, repository)
        return requests.post(self.url(uri), json=data, **self.request_params)

    def create_content(self, path, labels):
        """
        Create content for a given artifact
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Content:-Packages/operation/content_rpm_packages_create
        """
        uri = "/api/v3/content/rpm/packages/upload/"
        with open(path, "rb") as fp:
            data = {"pulp_labels": json.dumps(labels)}
            files = {"file": fp}
            self.log.info("Pulp: create_content: %s %s", uri, path)
            package = requests.post(
                self.url(uri), data=data, files=files, **self.request_params)
        return package

    def modify_repository_content_locked(self, repository, batch):
        """
        Creates a new repository version and a new publication. Executed under lock.
        """
        if batch.check_processed():
            self.log.info("Task processed by other process")
            return True

        # Merge others' tasks with ours (if any).
        data = batch.options()
        if not data["add_content_units"] and not data["remove_content_units"]:
            # No RPMs to add or remove
            return True
        # Make the request to create a new repository version
        response = self.modify_repository_content(repository, **data)
        if not response.ok:
            self.log.error("Failed to create a new repository version for: %s, %s",
                           repository, response.text)
            return False
        task = response.json()["task"]
        response = self.wait_for_finished_task(task)
        data = response.json()
        if response.ok and data["state"] == "completed":
            self.log.info("Successfully modified Pulp repository content %s", repository)
        else:
            self.log.info("Failed to modify Pulp repository content %s", repository)
            return False

        # Make a request to create a new publication
        response = self.create_publication(repository)
        task = response.json()["task"]
        response = self.wait_for_finished_task(task)
        data = response.json()
        if response.ok and data["state"] == "completed":
            self.log.info("Successfully created Pulp publication of repository %s", repository)
            return True
        self.log.info("Failed to create Pulp publication of repository %s", repository)
        return False

    def try_lock(self, repository, batch):
        """
        Periodically try to acquire the lock, and execute the modify_repository_content_locked() method.
        """

        while True:

            # We don't have fair locking (locks-first => processes-first).  So to
            # avoid potential indefinite waiting (see issue #1423) we check if the
            # task isn't already processed _without_ having the lock.

            if batch.check_processed(delete_if_not=False):
                self.log.info("Task processed by other process (no-lock)")
                return

            try:
                lockdir = os.environ.get(
                    "COPR_TESTSUITE_LOCKPATH", "/var/lock/copr-backend")
                with lock(repository, lockdir=lockdir, timeout=5, log=self.log):
                    if self.modify_repository_content_locked(repository, batch):
                        # While we still hold the lock, notify others we processed their
                        # task.  Note that we do not commit in case of random exceptions
                        # above.
                        batch.commit()
                        self.log.debug("Repository version and Publication created by this process")
                        break

            except LockTimeout:
                continue  # Try again...

            # we never loop, only upon timeout
            assert False

    def modify_repository_content(self, repository, add_content_units, remove_content_units):
        """
        Add and/or remove a list of artifacts to/from a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        path = os.path.join(repository, "modify/")
        url = self.config["base_url"] + path
        data = {"add_content_units": add_content_units or [], "remove_content_units": remove_content_units or []}
        return requests.post(url, json=data, **self.request_params)

    def add_content(self, repository, artifacts):
        """
        Add a list of artifacts to a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        batch = BatchedAddRemoveContent(repository, artifacts, None, self.opts, self.log)
        # Put our task to Redis DB and allow _others_ to process our
        # own task.  This needs to be run _before_ the lock() call.
        batch.make_request()
        self.try_lock(repository, batch)
        self.log.info("Pulp: add_content: %s (%s)", repository, artifacts)
        return True

    def delete_content(self, repository, artifacts):
        """
        Delete a list of artifacts from a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        batch = BatchedAddRemoveContent(repository, None, artifacts, self.opts, self.log)
        # Put our task to Redis DB and allow _others_ to process our
        # own task.  This needs to be run _before_ the lock() call.
        batch.make_request()
        self.try_lock(repository, batch)
        self.log.info("Pulp: delete_content: %s (%s)", repository, artifacts)
        return True

    def get_content(self, build_ids):
        """
        Get a list of PRNs for RPMs with provided build ids
        https://pulpproject.org/pulp_rpm/restapi/#tag/Content:-Packages/operation/content_rpm_packages_list
        """
        query = ""
        for build_id in build_ids:
            if query:
                query += " OR "
            query += f"pulp_label_select=\"build_id={build_id}\""
        uri = "api/v3/content/rpm/packages/?"
        # Setting the limit to 1000, but in the future we should use pagination
        uri += urlencode({"q": query, "fields": "prn", "offset": 0, "limit": 1000})
        self.log.info("Pulp: get_content: %s, query = %s", uri, query)
        return requests.get(self.url(uri), **self.request_params)

    def delete_repository(self, repository):
        """
        Delete an RPM repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_delete
        """
        url = self.config["base_url"] + repository
        self.log.info("Pulp: delete_repository: %s", repository)
        return requests.delete(url, **self.request_params)

    def delete_distribution(self, distribution):
        """
        Delete an RPM distribution
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_delete
        """
        url = self.config["base_url"] + distribution
        self.log.info("Pulp: delete_distribution: %s", distribution)
        return requests.delete(url, **self.request_params)

    def wait_for_finished_task(self, task, timeout=86400):
        """
        Pulp task (e.g. creating a publication) can be running for an
        unpredictably long time. We need to wait until it is finished to know
        what it actually did.
        """
        start = time.time()
        while True:
            self.log.info("Pulp: polling task status: %s", task)
            response = self.get_task(task)
            if not response.ok:
                break
            if response.json()["state"] not in ["waiting", "running"]:
                break
            if time.time() > start + timeout:
                break
            time.sleep(5)
        return response

    def list_distributions(self, prefix):
        """
        Get a list of distributions whose names match a given prefix
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_list
        """
        uri = "api/v3/distributions/rpm/rpm/?"
        uri += urlencode({"name__startswith": prefix})
        self.log.info("Pulp: list_distributions: %s", uri)
        return requests.get(self.url(uri), **self.request_params)

    def set_label(self, href, name, value):
        """
        Set a label on a given object
        https://pulpproject.org/pulp_rpm/restapi/#tag/Content:-Packages/operation/content_rpm_packages_set_label
        """
        uri = href + "set_label/"
        data = {"key": name, "value": value}
        self.log.info("Pulp: set_label: %s", uri)
        return requests.post(self.url(uri), json=data, **self.request_params)
