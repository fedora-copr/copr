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
    def create_from_config_file(cls, path=None, log=None):
        """
        Create a Pulp client from a standard configuration file that is
        used by the `pulp` CLI tool
        """
        path = os.path.expanduser(path or "~/.config/pulp/cli.toml")
        with open(path, "rb") as fp:
            config = tomllib.load(fp)
        return cls(config["cli"], log)

    def __init__(self, config, log=None):
        self.config = config
        self.timeout = 60
        self.log = log or logging.getLogger(__name__)

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

    def update_distribution(self, distribution, publication):
        """
        Update an RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_update
        """
        self.log.info("Pulp: updating distribution %s", distribution)
        url = self.config["base_url"] + distribution
        data = {
            "publication": publication,
            # When we create a distribution, we point it to a repository. Now we
            # want to point it to a publication, so we need to reset the,
            # repository. Otherwise we will get "Only one of the attributes
            # 'repository' and 'publication' may be used simultaneously."
            "repository": None,
        }
        return requests.patch(url, json=data, **self.request_params)

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

    def add_content(self, repository, artifacts):
        """
        Add a list of artifacts to a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        path = os.path.join(repository, "modify/")
        url = self.config["base_url"] + path
        data = {"add_content_units": artifacts}
        self.log.info("Pulp: add_content: %s %s", path, artifacts)
        return requests.post(url, json=data, **self.request_params)

    def delete_content(self, repository, artifacts):
        """
        Delete a list of artifacts from a repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_modify
        """
        path = os.path.join(repository, "modify/")
        url = self.config["base_url"] + path
        data = {"remove_content_units": artifacts}
        self.log.info("Pulp: delete_content: %s (%s)", path, artifacts)
        return requests.post(url, json=data, **self.request_params)

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
