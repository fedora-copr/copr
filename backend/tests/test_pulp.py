"""
Test Pulp client
"""

# pylint: disable=attribute-defined-outside-init

from copr_backend.pulp import PulpClient


class TestPulp:

    def setup_method(self, _method):
        self.config = {
            "api_root": "/pulp/",
            "base_url": "http://pulp.fpo:24817",
            "cert": "",
            "domain": "default",
            "dry_run": False,
            "format": "json",
            "key": "",
            "password": "1234",
            "timeout": 0,
            "username": "admin",
            "verbose": 0,
            "verify_ssl": True,
        }

    def test_url(self):
        client = PulpClient(self.config)
        assert self.config["domain"] == "default"
        assert client.url("api/v3/artifacts/")\
            == "http://pulp.fpo:24817/pulp/api/v3/artifacts/"

        assert client.url("api/v3/repositories/rpm/rpm/?")\
            == "http://pulp.fpo:24817/pulp/api/v3/repositories/rpm/rpm/?"

        self.config["domain"] = "copr"
        assert client.url("api/v3/artifacts/")\
            == "http://pulp.fpo:24817/pulp/copr/api/v3/artifacts/"
