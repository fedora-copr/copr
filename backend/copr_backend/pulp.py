"""
Pulp doesn't provide an API client, we are implementing it for ourselves
"""

import os
import tomllib
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
    def create_from_config_file(cls, path=None):
        """
        Create a Pulp client from a standard configuration file that is
        used by the `pulp` CLI tool
        """
        path = os.path.expanduser(path or "~/.config/pulp/cli.toml")
        with open(path, "rb") as fp:
            config = tomllib.load(fp)
        return cls(config["cli"])

    def __init__(self, config):
        self.config = config
        self.timeout = 60

    @property
    def auth(self):
        """
        https://requests.readthedocs.io/en/latest/user/authentication/
        """
        return (self.config["username"], self.config["password"])

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
        return {"auth": self.auth, "timeout": self.timeout}

    def create_repository(self, name):
        """
        Create an RPM repository
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_create
        """
        url = self.url("api/v3/repositories/rpm/rpm/")
        data = {"name": name}
        return requests.post(url, json=data, **self.request_params)

    def get_repository(self, name):
        """
        Get a single RPM repository
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_list
        """
        # There is no endpoint for querying a single repository by its name,
        # even Pulp CLI does this workaround
        url = self.url("api/v3/repositories/rpm/rpm/?")
        url += self._urlencode({"name": name, "offset": 0, "limit": 1})
        return requests.get(url, **self.request_params)

    def get_distribution(self, name):
        """
        Get a single RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_list
        """
        # There is no endpoint for querying a single repository by its name,
        # even Pulp CLI does this workaround
        url = self.url("api/v3/distributions/rpm/rpm/?")
        url += self._urlencode({"name": name, "offset": 0, "limit": 1})
        return requests.get(url, **self.request_params)

    def get_task(self, task):
        """
        Get a detailed information about a task
        """
        url = self.config["base_url"] + task
        return requests.get(url, **self.request_params)
    def _urlencode(self, query):
        """
        Join a dict into URL query string but don't encode special characters
        https://docs.python.org/3/library/urllib.parse.html#urllib.parse.urlencode
        Our repository names are e.g. frostyx/test-pulp/fedora-39-x86_64.
        The standard urlencode would change the slashes to %2F making Pulp to
        not find the project when filtering by name.
        """
        return "&".join([f"{k}={v}" for k, v in query.items()])

    def create_distribution(self, name, repository, basepath=None):
        """
        Create an RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_create
        """
        url = self.url("api/v3/distributions/rpm/rpm/")
        data = {
            "name": name,
            "repository": repository,
            "base_path": basepath or name,
        }
        return requests.post(url, json=data, **self.request_params)

    def create_publication(self, repository):
        """
        Create an RPM publication
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Publications:-Rpm/operation/publications_rpm_rpm_create
        """
        url = self.url("api/v3/publications/rpm/rpm/")
        data = {"repository": repository}
        return requests.post(url, json=data, **self.request_params)

    def update_distribution(self, distribution, publication):
        """
        Update an RPM distribution
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_update
        """
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

    def create_content(self, repository, artifact, relative_path):
        """
        Create content for a given artifact
        https://docs.pulpproject.org/pulp_rpm/restapi.html#tag/Content:-Packages/operation/content_rpm_packages_create
        """
        url = self.url("api/v3/content/rpm/packages/")
        data = {
            "repository": repository,
            "artifact": artifact,
            "relative_path": relative_path,
        }
        return requests.post(url, json=data, **self.request_params)

    def upload_artifact(self, path):
        """
        Create an artifact
        https://docs.pulpproject.org/pulpcore/restapi.html#tag/Artifacts/operation/artifacts_create
        """
        with open(path, "rb") as fp:
            url = self.url("api/v3/artifacts/")
            data = {"file": fp}
            return requests.post(url, files=data, **self.request_params)

    def delete_repository(self, repository):
        """
        Delete an RPM repository
        https://pulpproject.org/pulp_rpm/restapi/#tag/Repositories:-Rpm/operation/repositories_rpm_rpm_delete
        """
        url = self.config["base_url"] + repository
        return requests.delete(url, **self.request_params)

    def delete_distribution(self, distribution):
        """
        Delete an RPM distribution
        https://pulpproject.org/pulp_rpm/restapi/#tag/Distributions:-Rpm/operation/distributions_rpm_rpm_delete
        """
        url = self.config["base_url"] + distribution
        return requests.delete(url, **self.request_params)
