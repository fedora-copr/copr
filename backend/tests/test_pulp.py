"""
Test Pulp client
"""

# pylint: disable=attribute-defined-outside-init

from unittest.mock import Mock
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

    def create_mock_response(self, results, count, next_url=None, ok=True):
        mock_response = Mock()
        mock_response.ok = ok
        mock_response.status_code = 200 if ok else 400
        mock_response.text = "OK" if ok else "Error"
        mock_response.json.return_value = {
            "count": count,
            "next": next_url,
            "previous": None,
            "results": results
        }
        return mock_response

    def test_get_content_pagination_single_page(self):
        client = PulpClient(self.config)

        results = [{"prn": f"rpm-{i}"} for i in range(50)]
        mock_response = self.create_mock_response(results, 50, next_url=None)
        client.send = Mock(return_value=mock_response)

        response = client.get_content([1234], fields=["prn"])

        assert response.ok
        data = response.json()
        assert data["count"] == 50
        assert len(data["results"]) == 50
        assert data["next"] is None
        assert all(item["prn"] == f"rpm-{i}" for i, item in enumerate(data["results"]))

        assert client.send.call_count == 1

    def test_get_content_pagination_multiple_pages(self):
        client = PulpClient(self.config)

        def mock_send(_, uri):
            if "offset=0" in uri:
                # First page
                results = [{"prn": f"rpm-{i}"} for i in range(1000)]
                return self.create_mock_response(
                    results, 2500, next_url="http://test/api/v3/content/rpm/packages/?offset=1000"
                )
            if "offset=1000" in uri:
                # Second page
                results = [{"prn": f"rpm-{i}"} for i in range(1000, 2000)]
                return self.create_mock_response(
                    results, 2500, next_url="http://test/api/v3/content/rpm/packages/?offset=2000"
                )
            if "offset=2000" in uri:
                # Third page (partial)
                results = [{"prn": f"rpm-{i}"} for i in range(2000, 2500)]
                return self.create_mock_response(results, 2500, next_url=None)
            return self.create_mock_response([], 2500, next_url=None)

        client.send = Mock(side_effect=mock_send)

        response = client.get_content([1234, 5678], fields=["prn"])

        assert response.ok
        data = response.json()
        assert data["count"] == 2500
        assert len(data["results"]) == 2500
        assert data["next"] is None
        assert all(item["prn"] == f"rpm-{i}" for i, item in enumerate(data["results"]))

        assert client.send.call_count == 3

    def test_get_content_pagination_error_handling(self):
        client = PulpClient(self.config)
        error_response = self.create_mock_response([], 0, ok=False)
        client.send = Mock(return_value=error_response)
        response = client.get_content([1234])

        assert not response.ok
        assert client.send.call_count == 1
