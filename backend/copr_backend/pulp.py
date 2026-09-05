"""
Pulp doesn't provide an API client, we are implementing it for ourselves
"""

import io
import json
import logging
import os
import shutil
import time
import tomllib
import hashlib
from itertools import batched
from urllib.parse import urlencode

from copr_common.request import SafeRequest
from copr_common.lock import Lock
from copr_common.redis_helpers import get_redis_connection
from copr_backend.helpers import format_filename


# JSON data in a POST request can be large but they probably cannot be
# unlimited. Also, the more package we specify in one request, the longer it
# takes Pulp to process it. And at some point (around 50k) it gets too slow and
# the requests starts timeouting.
# So how many PRNs are we going to send per one request?
MAX_CONTENT_UNITS_IN_BATCH = 10000


class PaginatedResponse:
    """
    A response-like object that maintains backward compatibility with PULP API responses
    while containing all paginated results.
    """
    def __init__(self, all_results, original_response):
        self._all_results = all_results
        self._original_response = original_response

        self.status_code = original_response.status_code
        self.ok = original_response.ok
        self.text = original_response.text

    def json(self):
        """
        Mimic Pulp paginated response, but with all results included
        """
        return {
            "count": len(self._all_results),
            "next": None,  # All results are included
            "previous": None,
            "results": self._all_results
        }

    def raise_for_status(self):
        """
        Mimic requests.Response.raise_for_status()
        """
        self._original_response.raise_for_status()


class BatchedAddRemoveContent:
    """
    Group a set of `add_and_remove` tasks for a single Pulp repository.
    """
    def __init__(self, repo_href, rpms_to_add, rpms_to_remove, backend_opts=None,
                 log=None, noop=False, dirs_to_delete=None, client=None):
        self.repo_href = repo_href
        self.rpms_to_add = rpms_to_add or []
        self.rpms_to_remove = rpms_to_remove or []
        self.dirs_to_delete = dirs_to_delete or []
        self.log = log
        self.noop = noop
        self.client = client

        if not backend_opts:
            self.log.error("can't get access to redis, batch disabled")
            self.noop = True
            return

        self._pid = os.getpid()
        self._json_redis_task = json.dumps({
            "add_content_units": self.rpms_to_add,
            "remove_content_units": self.rpms_to_remove,
            "dirs_to_delete": self.dirs_to_delete,
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
        dirs_to_delete = set(self.dirs_to_delete)

        if self.noop:
            return {"add_content_units": rpms_to_add,
                    "remove_content_units": rpms_to_remove,
                    "dirs_to_delete": dirs_to_delete}

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

            units = len(task_opts["add_content_units"])
            units += len(task_opts["remove_content_units"])
            if units > MAX_CONTENT_UNITS_IN_BATCH:
                self.log.info(
                    "Limit %s of units per request reached, skip the rest",
                    MAX_CONTENT_UNITS_IN_BATCH,
                )
                break

            # we can process this task!
            self.notify_keys.append(key)

            # append "add" tasks, if that makes sense
            rpms_to_add.update(task_opts["add_content_units"])
            rpms_to_remove.update(task_opts["remove_content_units"])
            dirs_to_delete.update(task_opts.get("dirs_to_delete", []))

        # Make sure we are not adding and removing the same packages
        common = rpms_to_add & rpms_to_remove
        rpms_to_add -= common
        rpms_to_remove -= common

        # Make sure we are not trying to add the same NEVRAs in one request
        rpms_to_add = self._unique_nevras(rpms_to_add)

        return {"add_content_units": list(rpms_to_add),
                "remove_content_units": list(rpms_to_remove),
                "dirs_to_delete": list(dirs_to_delete)}

    def _unique_nevras(self, hrefs_or_prns):
        unique = {}
        for href_or_prn in hrefs_or_prns:
            if href_or_prn.startswith("prn:"):
                data = self.client.get_package_by_prn(href_or_prn).json()
            else:
                data = self.client.get_by_href(href_or_prn).json()

            # We are intentionally leaving out epoch because Pulp cannot handle
            # two different epochs in one repository
            # https://github.com/pulp/pulp_rpm/issues/4239
            nevra = format_filename(
                data["name"],
                data["version"],
                data["release"],
                "",
                data["arch"],
            )

            if nevra in unique:
                self.log.warning("Duplicate NEVRA in one request: %s ", nevra)

            build_id = int(data["pulp_labels"]["build_id"])
            if nevra not in unique or unique[nevra][1] < build_id:
                unique[nevra] = (href_or_prn, build_id)

        self.log.info("Unique NEVRAs: %s", list(unique.keys()))
        return {x[0] for x in unique.values()}

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

    def _execute_locked(self, repository):
        """
        Creates a new repository version and a new publication. Executed under lock.
        """
        if self.check_processed():
            self.log.info("Task processed by other process")
            return

        data = self.options()
        dirs_to_delete = data.pop("dirs_to_delete", [])

        try:
            if not data["add_content_units"] and not data["remove_content_units"]:
                return
            self.client.deliver_and_wait([
                self.client.modify_repository_content(repository, **data),
            ])
            self.client.deliver_and_wait([
                self.client.publish(repository),
            ])
        finally:
            self._delete_dirs(dirs_to_delete)

    def _delete_dirs(self, dirs_to_delete):
        for path in dirs_to_delete:
            self.log.info("Removing directory %s", path)
            shutil.rmtree(path)

    def try_lock(self, repository):
        """
        Acquire the lock and execute the _execute_locked() method.
        """
        with Lock(self.redis, self.log).lock(repository):
            self._execute_locked(repository)
            self.commit()


class PulpRequest:
    """
    A deferred Pulp API request that can be submitted and waited on.
    """
    def __init__(self, method, url, data=None, description=""):
        self.method = method
        self.url = url
        self.data = data
        self.description = description


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
        return (self.config.get("cert"), self.config.get("key"))

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

    def send(self, method, url, data=None, files=None, headers=None, timeout=None):
        """
        Performs a "safe request", meaning that if a request fails, we wait
        and try again, and again, until it succeeds.
        """
        # pylint: disable=too-many-positional-arguments
        request = SafeRequest(
            log=self.log,
            try_indefinitely=True,
            timeout=timeout or self.timeout,
            user_agent="crc-pulp-client",
        )
        if all(self.cert):
            request.cert = self.cert
        else:
            request.auth = self.auth

        # If only URI was passed, make it a fully qualified URL
        if not url.startswith(("http://", "https://")):
            url = self.url(url)

        response = request.send(
            url=url,
            method=method,
            data=data,
            files=files,
            headers=headers,
        )
        return response

    def create_repository(self, name, persistent=False):
        """
        Build a PulpRequest to create an RPM repository.
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_create
        """
        uri = "/api/v3/repositories/rpm/rpm/"
        data = {
            "name": name,
            "retain_repo_versions": 1,
            # Temporarily retain all packages, workaround for #4071
            "retain_package_versions": 0 if persistent else 0,
        }
        return PulpRequest("POST", uri, data,
                           f"create repository {name}")

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
        return self.send("GET", uri)

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
        return self.send("GET", uri)

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
        return self.send("GET", url)

    def get_package_by_prn(self, prn):
        """
        Get a detailed information about a package
        """
        pulp_id = prn.rsplit(":", 1)[1]
        uri = f"/api/v3/content/rpm/packages/{pulp_id}/"
        self.log.info("Pulp: get_by_prn: %s", uri)
        return self.send("GET", uri)

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
        return PulpRequest("POST", uri, data,
                           f"create distribution {name}")

    def update_distribution(self, distribution, publication=None,
                            repository=None):
        """
        Build a PulpRequest to update an RPM distribution.
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_update

        This allows us to point a distribution to either a publication or
        a repository. Not both, that doesn't make sense and Pulp would raise
        "Only one of the attributes 'repository' and 'publication' may be used simultaneously."
        """
        if publication and repository:
            raise RuntimeError("Specify either publication or repository")

        url = self.config["base_url"] + distribution
        data = {
            "publication": publication,
            "repository": repository,
        }
        return PulpRequest("PATCH", url, data,
                           f"update distribution {distribution}")

    def publish(self, repository):
        """
        Build a PulpRequest to create an RPM publication.
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Publications:-Rpm/operation/publications_rpm_rpm_create
        """
        uri = "/api/v3/publications/rpm/rpm/"
        data = {"repository": repository}
        return PulpRequest("POST", uri, data, f"publish {repository}")

    def get_publication(self, repository):
        """
        Get a single RPM publication
        https://pulpproject.org/pulp_rpm/restapi/#tag/Publications:-Rpm/operation/publications_rpm_rpm_list
        """
        # There is no endpoint for querying a single publication
        uri = "/api/v3/publications/rpm/rpm/?"
        uri += urlencode({"repository": repository, "offset": 0, "limit": 1})
        self.log.info("Pulp: get_publication: %s", uri)
        return self.send("GET", uri)

    def create_content(self, path, labels, timeout=3600):
        """
        Create content for a given artifact
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Content:-Packages/operation/content_rpm_packages_create
        """
        uri = "/api/v3/content/rpm/packages/upload/"
        with open(path, "rb") as fp:
            data = {"pulp_labels": json.dumps(labels)}
            files = {"file": fp}
            self.log.info("Pulp: create_content: %s %s", uri, path)
            package = self.send("POST", uri, data=data, files=files, timeout=timeout)
        return package

    def create_content_chunked(self, path, labels):
        """
        Split a file into chunks, upload them and reassemble them on the Pulp
        side.
        https://pulpproject.org/pulpcore/docs/user/guides/upload-publish/?h=chunked#chunked-uploads
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Content:-Packages/operation/content_rpm_packages_create
        """
        # Send an initial request, saying that we want to chunk-upload a file
        # of a given size
        uri = "/api/v3/uploads/"
        data = {
            "size": os.path.getsize(path),
        }
        response = self.send("POST", uri, data)
        upload_href = response.json()["pulp_href"]
        upload_url = self.config["base_url"] + upload_href

        with open(path, "rb") as fp:
            sha256 = hashlib.file_digest(fp, "sha256")

        # Upload the chunks
        size = 1024 * 1024 * 100
        for i, chunk in enumerate(self._read_chunks(path, size=size)):
            # Figure out the start and end byte of the chunk within the whole
            # file
            start = i * size
            end = start + len(chunk) - 1
            headers = {
                "Content-Range": "bytes {0}-{1}/*".format(start, end),
            }
            files = {
                "file": (
                    # Filename
                    "chunk{0}".format(i),

                    # Content from bytes that we already have in the memory
                    io.BytesIO(chunk),

                    # A generic MIME type for binary files
                    "application/octet-stream",
                ),
            }
            response = self.send(
                "PUT",
                upload_url,
                files=files,
                headers=headers,
            )
            if not response.ok:
                raise RuntimeError(
                    "Failed to upload chunk {0} of {1}: {2}"
                    .format(i, path, response.reason)
                )

        # Send the file request that we want to reassemble the file
        commit_url = self.config["base_url"] + upload_href + "commit/"
        commit_data = {
            "sha256": sha256.hexdigest(),
        }

        # We need to wait until the task finishes. This is the disadvantage
        # compared to standard uploads
        data = self.deliver_and_wait([
            PulpRequest("POST", commit_url, commit_data,
                        f"upload chunked {path}"),
        ])[0]

        resources = data["created_resources"]
        if len(resources) != 1:
            raise RuntimeError("Unexpected number of created files: {0}".format(resources))

        uri = "/api/v3/content/rpm/packages/upload/"
        data = {
            "artifact": resources[0],
            "pulp_labels": json.dumps(labels),
        }
        self.log.info("Pulp: create_content: %s for artifact %s", uri, resources[0])
        response = self.send("POST", uri, data=data)
        self.log.info("Successfully created a content for chunked uploaded %s", path)
        return response

    def _read_chunks(self, path, size=10000):
        """
        Generate chunks of a given file
        """
        with open(path, "rb") as fp:
            while content := fp.read(size):
                yield content

    def modify_repository_content(self, repository, add_content_units, remove_content_units):
        """
        Build a PulpRequest to add/remove artifacts to/from a repository.
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        path = os.path.join(repository, "modify/")
        url = self.config["base_url"] + path
        data = {"add_content_units": add_content_units or [], "remove_content_units": remove_content_units or []}
        return PulpRequest("POST", url, data,
                           f"modify repository content {repository}")

    def add_content(self, repository, artifacts):
        """
        Add a list of artifacts to a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        size = MAX_CONTENT_UNITS_IN_BATCH
        pages = [list(x) for x in batched(artifacts, size)]
        for i, page in enumerate(pages, start=1):
            batch = BatchedAddRemoveContent(
                repository, page, None, self.opts, self.log, client=self)
            # Put our task to Redis DB and allow _others_ to process our
            # own task.  This needs to be run _before_ try_lock().
            batch.make_request()
            batch.try_lock(repository)
            self.log.info(
                "Pulp: add_content: %s (%s) [%s/%s]",
                repository, page, i, len(pages),
            )
        return True

    def delete_content(self, repository, artifacts, dirs_to_delete=None):
        """
        Delete a list of artifacts from a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        size = MAX_CONTENT_UNITS_IN_BATCH
        pages = [list(x) for x in batched(artifacts, size)]
        for i, page in enumerate(pages, start=1):
            batch = BatchedAddRemoveContent(
                repository, None, page, self.opts, self.log,
                dirs_to_delete=dirs_to_delete, client=self)
            # Put our task to Redis DB and allow _others_ to process our
            # own task.  This needs to be run _before_ try_lock().
            batch.make_request()
            batch.try_lock(repository)
            self.log.info(
                "Pulp: delete_content: %s (%s) [%s/%s]",
                repository, page, i, len(pages),
            )
        return True

    def get_content(self, build_ids, chroot=None, fields=None):
        """
        Get a list of PRNs for RPMs with provided build ids
        https://pulpproject.org/pulp_rpm/restapi/#tag/Content:-Packages/operation/content_rpm_packages_list
        """
        if not build_ids:
            raise ValueError("Content must be queried for specific builds")

        all_results = []
        # We need to chunk the `build_ids` into lists of only 7 items otherwise
        # we are going to hit validation error from Pulp
        # See https://github.com/fedora-copr/copr/issues/4187
        # See https://github.com/pulp/pulpcore/issues/7435
        for batch in batched(build_ids, 7):
            results, response = self._get_content(batch, chroot, fields)
            all_results.extend(results)
        return PaginatedResponse(all_results, response)

    def _get_content(self, build_ids, chroot=None, fields=None):
        query = ""
        for i, build_id in enumerate(build_ids):
            if i:
                query += " OR "
            query += "("
            query += f"pulp_label_select=\"build_id={build_id}"
            if chroot:
                query += f",chroot={chroot}\""
            else:
                query += "\""
            query += ")"

        all_results = []
        offset = 0
        limit = 1000

        while True:
            params = {"q": query, "offset": offset, "limit": limit}
            if fields:
                params["fields"] = ",".join(fields)

            uri = "api/v3/content/rpm/packages/?" + urlencode(params)
            self.log.debug("Pulp: get_content: fetching page (offset=%d)", offset)

            response = self.send("GET", uri)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            self.log.debug("Pulp: get_content: fetched %d items", len(results))

            all_results.extend(results)

            next_url = data.get("next")
            if not next_url or len(results) == 0:
                break

            offset += limit

        self.log.info("Pulp: get_content: fetched %d items", len(all_results))
        return all_results, response

    def delete_repository(self, repository):
        """
        Delete an RPM repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_delete
        """
        url = self.config["base_url"] + repository
        return PulpRequest("DELETE", url,
                           description=f"delete repository {repository}")

    def delete_distribution(self, distribution):
        """
        Delete an RPM distribution
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_delete
        """
        url = self.config["base_url"] + distribution
        return PulpRequest("DELETE", url,
                           description=f"delete distribution {distribution}")

    def deliver_and_wait(self, requests, timeout=86400):
        """
        Submit multiple PulpRequests and wait for all background tasks to
        finish.  Retry failed requests/tasks until timeout.  Raise
        RuntimeError if any request cannot be completed within the timeout.
        """
        if not requests:
            return []

        deadline = time.monotonic() + timeout
        results = [None] * len(requests)

        # Initialize the todo-list.
        # (index, request, task_href_or_None, backoff_sleep)
        pending = [(i, req, None, 5) for i, req in enumerate(requests)]

        while pending:
            if time.monotonic() > deadline:
                descriptions = ", ".join(
                    req.description for _, req, _, _ in pending)
                raise RuntimeError(
                    f"Pulp tasks timed out after {timeout}s: {descriptions}")

            still_pending = []
            for i, req, task, backoff_sleep in pending:
                if task is None:
                    self.log.info("Pulp: submitting %s", req.description)
                    response = self.send(req.method, req.url, req.data)
                    if response.status_code != 202:
                        results[i] = response.json()
                        continue
                    task = response.json()["task"]
                    self.log.info("Pulp: %s => task %s",
                                  req.description, task)
                    still_pending.append((i, req, task, backoff_sleep))
                    continue

                response = self.get_task(task)
                data = response.json()
                if data["state"] in ("waiting", "running"):
                    still_pending.append((i, req, task, backoff_sleep))
                    continue
                if data["state"] == "completed":
                    self.log.info("Pulp %s %s succeeded",
                                  req.description, task)
                    results[i] = data
                    continue
                self.log.warning("Pulp %s %s failed, resubmitting: %s",
                                  req.description, task, data)
                # Re-add with None href.
                still_pending.append((i, req, None,
                                      min(backoff_sleep * 2, 300)))

            pending = still_pending
            if pending:
                time.sleep(max(s for _, _, _, s in pending))

        return results

    def list_distributions(self, prefix):
        """
        Get a list of distributions whose names match a given prefix
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_list
        """
        uri = "api/v3/distributions/rpm/rpm/?"
        uri += urlencode({"name__startswith": prefix})
        self.log.info("Pulp: list_distributions: %s", uri)
        return self.send("GET", uri)

    def set_label(self, href, name, value):
        """
        Set a label on a given object
        https://pulpproject.org/pulp_rpm/restapi/#tag/Content:-Packages/operation/content_rpm_packages_set_label
        """
        uri = href + "set_label/"
        data = {"key": name, "value": value}
        self.log.info("Pulp: set_label: %s", uri)
        return self.send("POST", uri, data)
