"""
Test Pulp client
"""

# pylint: disable=attribute-defined-outside-init

from unittest.mock import Mock, patch
import pytest
from copr_backend.pulp import PulpClient, PulpRequest


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

    def test_get_content_build_ids_batched(self):
        client = PulpClient(self.config)
        results = [{"prn": f"rpm-{i}"} for i in range(50)]
        mock_response = self.create_mock_response(results, 50, next_url=None)
        client.send = Mock(return_value=mock_response)

        build_ids = list(range(25))
        response = client.get_content(build_ids, fields=["prn"])
        assert client.send.call_count == 4
        assert client.send.call_args_list[0].args[1].count("build_id") == 7
        assert client.send.call_args_list[1].args[1].count("build_id") == 7
        assert client.send.call_args_list[2].args[1].count("build_id") == 7
        assert client.send.call_args_list[3].args[1].count("build_id") == 4

        assert response.ok
        assert response.json()["count"] == 200

    def test_get_content_build_ids_empty(self):
        client = PulpClient(self.config)
        client.send = Mock()
        with pytest.raises(ValueError) as ex:
            client.get_content([], fields=["prn"])
        assert "Content must be queried for specific builds" in str(ex)
        assert not client.send.called

    def test_create_distribution_without_content_guard(self):
        client = PulpClient(self.config)
        request = client.create_distribution("foo", "/repo/1/")
        assert request.data == {
            "name": "foo",
            "repository": "/repo/1/",
            "base_path": "foo",
        }

    def test_create_distribution_with_content_guard(self):
        client = PulpClient(self.config)
        request = client.create_distribution(
            "foo", "/repo/1/", content_guard="/guard/1/")
        assert request.data == {
            "name": "foo",
            "repository": "/repo/1/",
            "base_path": "foo",
            "content_guard": "/guard/1/",
        }

    def test_update_distribution_without_content_guard(self):
        client = PulpClient(self.config)
        request = client.update_distribution("/dist/1/", repository="/repo/1/")
        assert "content_guard" not in request.data

    def test_update_distribution_with_content_guard(self):
        client = PulpClient(self.config)
        request = client.update_distribution(
            "/dist/1/", content_guard="/guard/1/")
        assert request.data["content_guard"] == "/guard/1/"


class TestDeliverRequests:

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
        self.client = PulpClient(self.config)

    def _mock_response(self, status_code, json_data=None):
        resp = Mock()
        resp.ok = 200 <= status_code < 400
        resp.status_code = status_code
        resp.text = "mock"
        resp.json.return_value = json_data or {}
        return resp

    def test_empty_list(self):
        assert not self.client.deliver_and_wait([])

    @patch("time.sleep")
    def test_sync_request(self, _sleep):
        self.client.send = Mock(return_value=self._mock_response(
            201, {"pulp_href": "/repo/1/"}))
        req = PulpRequest("POST", "/api/v3/repositories/rpm/rpm/",
                          {"name": "test"}, "create repo")
        results = self.client.deliver_and_wait([req])
        assert results == [{"pulp_href": "/repo/1/"}]
        self.client.send.assert_called_once_with("POST",
            "/api/v3/repositories/rpm/rpm/", {"name": "test"})

    @patch("time.sleep")
    def test_async_task_completed(self, _sleep):
        submit_resp = self._mock_response(202, {"task": "/tasks/abc/"})
        task_resp = self._mock_response(200, {
            "state": "completed",
            "created_resources": ["/content/1/"],
        })
        self.client.send = Mock(return_value=submit_resp)
        self.client.get_task = Mock(return_value=task_resp)

        req = PulpRequest("POST", "/url/", None, "test task")
        results = self.client.deliver_and_wait([req])
        assert results[0]["state"] == "completed"
        self.client.get_task.assert_called_once_with("/tasks/abc/")

    @patch("time.sleep")
    def test_async_task_waiting_then_completed(self, _sleep):
        submit_resp = self._mock_response(202, {"task": "/tasks/abc/"})
        waiting_resp = self._mock_response(200, {"state": "waiting"})
        completed_resp = self._mock_response(200, {
            "state": "completed",
            "created_resources": [],
        })
        self.client.send = Mock(return_value=submit_resp)
        self.client.get_task = Mock(side_effect=[waiting_resp, completed_resp])

        req = PulpRequest("DELETE", "/url/", None, "delete thing")
        results = self.client.deliver_and_wait([req])
        assert results[0]["state"] == "completed"
        assert self.client.get_task.call_count == 2
        _sleep.assert_called()

    @patch("time.sleep")
    def test_failed_task_resubmitted(self, _sleep):
        submit_resp = self._mock_response(202, {"task": "/tasks/1/"})
        failed_resp = self._mock_response(200, {"state": "failed"})
        resubmit_resp = self._mock_response(202, {"task": "/tasks/2/"})
        completed_resp = self._mock_response(200, {
            "state": "completed",
            "created_resources": [],
        })
        self.client.send = Mock(side_effect=[submit_resp, resubmit_resp])
        self.client.get_task = Mock(side_effect=[failed_resp, completed_resp])

        req = PulpRequest("POST", "/url/", None, "retry task")
        results = self.client.deliver_and_wait([req])
        assert results[0]["state"] == "completed"
        assert self.client.send.call_count == 2
        assert self.client.get_task.call_count == 2

    @patch("time.sleep")
    @patch("time.monotonic")
    def test_timeout_raises(self, mock_monotonic, _sleep):
        mock_monotonic.side_effect = [0, 0, 100]
        submit_resp = self._mock_response(202, {"task": "/tasks/1/"})
        waiting_resp = self._mock_response(200, {"state": "waiting"})
        self.client.send = Mock(return_value=submit_resp)
        self.client.get_task = Mock(return_value=waiting_resp)

        req = PulpRequest("POST", "/url/", None, "slow task")
        with pytest.raises(RuntimeError, match="timed out"):
            self.client.deliver_and_wait([req], timeout=10)

    @patch("time.sleep")
    def test_multiple_parallel_requests(self, _sleep):
        submit1 = self._mock_response(202, {"task": "/tasks/1/"})
        submit2 = self._mock_response(202, {"task": "/tasks/2/"})
        completed1 = self._mock_response(200, {
            "state": "completed", "result": "one"})
        completed2 = self._mock_response(200, {
            "state": "completed", "result": "two"})
        self.client.send = Mock(side_effect=[submit1, submit2])
        self.client.get_task = Mock(side_effect=[completed1, completed2])

        reqs = [
            PulpRequest("DELETE", "/repo/1/", None, "delete repo 1"),
            PulpRequest("DELETE", "/dist/1/", None, "delete dist 1"),
        ]
        results = self.client.deliver_and_wait(reqs)
        assert results[0]["result"] == "one"
        assert results[1]["result"] == "two"

    @patch("time.sleep")
    def test_backoff_increases_on_failure(self, mock_sleep):
        """
        Backoff doubles on each task failure and persists across resubmits.
        """
        submit_resp = self._mock_response(202, {"task": "/tasks/1/"})
        failed_resp = self._mock_response(200, {"state": "failed"})
        resubmit_resp = self._mock_response(202, {"task": "/tasks/2/"})
        failed_resp2 = self._mock_response(200, {"state": "failed"})
        resubmit_resp2 = self._mock_response(202, {"task": "/tasks/3/"})
        completed_resp = self._mock_response(200, {"state": "completed"})
        self.client.send = Mock(
            side_effect=[submit_resp, resubmit_resp, resubmit_resp2])
        self.client.get_task = Mock(
            side_effect=[failed_resp, failed_resp2, completed_resp])

        req = PulpRequest("POST", "/url/", None, "backoff task")
        results = self.client.deliver_and_wait([req])
        assert results[0]["state"] == "completed"
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleeps == [5, 10, 10, 20, 20]

    @patch("time.sleep")
    def test_backoff_capped_at_300(self, mock_sleep):
        """
        Backoff doubles on each failure but never exceeds 300s.
        """
        failed_resp = self._mock_response(200, {"state": "failed"})
        completed_resp = self._mock_response(200, {"state": "completed"})

        # 8 failures: backoff goes 5→10→20→40→80→160→320→640
        # but capped: 5→10→20→40→80→160→300→300
        task_responses = [failed_resp] * 8 + [completed_resp]
        submit_responses = [
            self._mock_response(202, {"task": f"/tasks/{i}/"})
            for i in range(9)
        ]
        self.client.send = Mock(side_effect=submit_responses)
        self.client.get_task = Mock(side_effect=task_responses)

        req = PulpRequest("POST", "/url/", None, "capped backoff")
        results = self.client.deliver_and_wait([req])
        assert results[0]["state"] == "completed"
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert max(sleeps) == 300
