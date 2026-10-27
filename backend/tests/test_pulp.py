"""
Test Pulp client
"""

# pylint: disable=attribute-defined-outside-init

from unittest.mock import Mock, patch

from munch import Munch
import pytest

from copr_common.enums import CreaterepoReason
from copr_common.request import RequestError
from copr_backend.pulp import PulpClient, PulpRequest
from copr_backend.storage import PulpStorage


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

    @patch("copr_backend.pulp.MAX_CONTENT_UNITS_IN_BATCH", 2)
    @patch("copr_backend.pulp.BatchedAddRemoveContent")
    def test_modify_content_pagination(self, mc_batch):
        """
        Content is modified in batches of at most MAX_CONTENT_UNITS_IN_BATCH
        units, the additions and the removals paginated together as one
        sequence (all the additions first).  An interrupted operation thus
        never leaves the repository without the content that it was about
        to replace, and an uneven split doesn't produce almost-empty
        requests.
        """
        client = PulpClient(self.config)

        client.modify_content("/repositories/rpm/rpm/repo/",
                              ["a", "b", "c"], ["x", "y"])

        pages = [call.args[1:3] for call in mc_batch.call_args_list]
        assert pages == [(["a", "b"], []), (["c"], ["x"]), ([], ["y"])]
        assert mc_batch.return_value.make_request.call_count == 3
        assert mc_batch.return_value.try_lock.call_count == 3

    def test_get_content_pagination_single_page(self):
        client = PulpClient(self.config)

        results = [{"prn": f"rpm-{i}", "pulp_href": "bar"} for i in range(50)]
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
                results = [{"prn": f"rpm-{i}", "pulp_href": "baz"} for i in range(1000)]
                return self.create_mock_response(
                    results, 2500, next_url="http://test/api/v3/content/rpm/packages/?offset=1000"
                )
            if "offset=1000" in uri:
                # Second page
                results = [{"prn": f"rpm-{i}", "pulp_href": "baz2"} for i in range(1000, 2000)]
                return self.create_mock_response(
                    results, 2500, next_url="http://test/api/v3/content/rpm/packages/?offset=2000"
                )
            if "offset=2000" in uri:
                # Third page (partial)
                results = [{"prn": f"rpm-{i}", "pulp_href": "baz3"} for i in range(2000, 2500)]
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
        results = [{"prn": f"rpm-{i}", "pulp_href": "foo"} for i in range(50)]
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

    def test_get_build_ids(self):
        """Builds of a repository are enumerated from its latest version."""
        client = PulpClient(self.config)

        repo_response = Mock()
        repo_response.json.return_value = {
            "latest_version_href": "/versions/42/"}
        client.get_by_href = Mock(return_value=repo_response)

        results = [
            {"pulp_labels": {"build_id": "123"}},
            {"pulp_labels": {"build_id": "456"}},
            # one more RPM of the first build
            {"pulp_labels": {"build_id": "123"}},
        ]
        client.send = Mock(return_value=self.create_mock_response(
            results, 3, next_url=None))

        build_ids = client.get_build_ids("/repositories/rpm/rpm/repo/")

        assert build_ids == [123, 456]
        uri = client.send.call_args_list[0].args[1]
        assert "repository_version=%2Fversions%2F42%2F" in uri
        assert "fields=pulp_labels" in uri

    def test_distribution_without_content_guard(self):
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

    def test_update_distribution_no_guard(self):
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
    def test_refused_request_doesnt_abort_batch(self, _sleep):
        """
        When Pulp refuses one of the requests, the rest of the batch is
        still submitted and waited for, and the error is re-raised at the
        end.
        """
        submit_resp = self._mock_response(202, {"task": "/tasks/2/"})
        completed_resp = self._mock_response(200, {
            "state": "completed", "result": "done"})
        error = RequestError("This field must be unique")
        self.client.send = Mock(side_effect=[error, submit_resp])
        self.client.get_task = Mock(return_value=completed_resp)

        reqs = [
            PulpRequest("POST", "/url/", None, "refused task"),
            PulpRequest("POST", "/url/", None, "valid task"),
        ]
        with pytest.raises(RequestError):
            self.client.deliver_and_wait(reqs)

        # The second request was submitted, and its task waited for
        assert self.client.send.call_count == 2
        self.client.get_task.assert_called_once_with("/tasks/2/")

    @patch("time.sleep")
    def test_multiple_refused_requests_aggregate(self, _sleep):
        """
        When Pulp refuses multiple requests, a RuntimeError with an
        aggregated message of all the failures is raised, chained from
        the first refused request's error.
        """
        error1 = RequestError("first problem")
        error2 = RequestError("second problem")
        submit_resp = self._mock_response(202, {"task": "/tasks/3/"})
        completed_resp = self._mock_response(200, {
            "state": "completed", "result": "done"})
        self.client.send = Mock(side_effect=[error1, error2, submit_resp])
        self.client.get_task = Mock(return_value=completed_resp)

        reqs = [
            PulpRequest("POST", "/url/", None, "refused task 1"),
            PulpRequest("POST", "/url/", None, "refused task 2"),
            PulpRequest("POST", "/url/", None, "valid task"),
        ]
        with pytest.raises(RuntimeError) as ex:
            self.client.deliver_and_wait(reqs)

        assert "2 of 3 Pulp requests failed" in str(ex.value)
        assert "refused task 1 (first problem)" in str(ex.value)
        assert "refused task 2 (second problem)" in str(ex.value)
        assert ex.value.__cause__ is error1

        # The whole batch was submitted before the error was raised
        assert self.client.send.call_count == 3
        self.client.get_task.assert_called_once_with("/tasks/3/")

    def _unique_error(self):
        response = Mock()
        response.text = "This field must be unique"
        return RequestError("This field must be unique", response=response)

    @patch("time.sleep")
    def test_exist_ok(self, _sleep):
        """
        With exist_ok, duplicate object creations don't raise,
        the request is simply dropped from the batch.
        """
        submit_resp = self._mock_response(202, {"task": "/tasks/3/"})
        completed_resp = self._mock_response(200, {
            "state": "completed", "result": "done"})
        self.client.send = Mock(side_effect=[
            self._unique_error(), self._unique_error(), submit_resp])
        self.client.get_task = Mock(return_value=completed_resp)

        reqs = [
            PulpRequest("POST", "/url/", None, "duplicate 1"),
            PulpRequest("POST", "/url/", None, "duplicate 2"),
            PulpRequest("POST", "/url/", None, "valid task"),
        ]
        results = self.client.deliver_and_wait(reqs, exist_ok=True)

        assert results[0] is None
        assert results[1] is None
        assert results[2]["result"] == "done"
        self.client.get_task.assert_called_once_with("/tasks/3/")

    @patch("time.sleep")
    def test_exist_ok_other_errors_raised(self, _sleep):
        """
        With exist_ok, only the duplicate creations are tolerated,
        all the other refusals are still re-raised at the end.
        """
        other_response = Mock()
        other_response.text = "Some other problem"
        other_error = RequestError("Some other problem",
                                   response=other_response)
        submit_resp = self._mock_response(202, {"task": "/tasks/2/"})
        completed_resp = self._mock_response(200, {
            "state": "completed", "result": "done"})
        self.client.send = Mock(side_effect=[
            self._unique_error(), other_error, submit_resp])
        self.client.get_task = Mock(return_value=completed_resp)

        reqs = [
            PulpRequest("POST", "/url/", None, "duplicate"),
            PulpRequest("POST", "/url/", None, "broken task"),
            PulpRequest("POST", "/url/", None, "valid task"),
        ]
        with pytest.raises(RequestError) as ex:
            self.client.deliver_and_wait(reqs, exist_ok=True)

        assert str(ex.value) == "Some other problem"
        # The whole batch was submitted before the error was re-raised
        assert self.client.send.call_count == 3
        self.client.get_task.assert_called_once_with("/tasks/2/")

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


class TestPulpStorageInitProject:
    """
    Test the batched initialization of Pulp repositories
    """

    def _response(self, results):
        response = Mock()
        response.json.return_value = {"results": results}
        return response

    def _request_error(self):
        response = Mock()
        response.text = "This field must be unique"
        return RequestError("This field must be unique", response=response)

    def _storage(self, devel=False):
        with patch("copr_backend.storage.get_redis_connection"), \
             patch("copr_backend.storage.PulpClient.create_from_config_file") \
                 as mc_factory:
            mc_factory.return_value = Mock()
            opts = Munch(pulp_content_guard="/guard/1/",
                         pulp_content_url="https://pulp.fpo")
            storage = PulpStorage(
                "owner", "project", False, devel, False, opts, Mock())
        return storage

    def _mock_client(self, storage, existing_repos=None, existing_dists=None,
                     fail_on=None, unique_on=None):
        """
        Mock the Pulp client of STORAGE so that the objects in
        EXISTING_REPOS/DISTS are reported as already created.  The
        deliver_and_wait() mock commits the pending "create" requests, and
        records all the request batches for later asserts.  Requests whose
        string starts with FAIL_ON raise RuntimeError.  Requests whose
        string starts with UNIQUE_ON raise RequestError ("This field must
        be unique"), as if a concurrent action created the same objects in
        the meantime.
        """
        existing_repos = set(existing_repos or [])
        existing_dists = set(existing_dists or [])
        client = storage.client
        batches = []

        def get_repository(name):
            if name in existing_repos:
                return self._response([{"pulp_href": "/repo" + name}])
            return self._response([])

        def get_distribution(name):
            if name in existing_dists:
                return self._response([{"pulp_href": "/dist" + name}])
            return self._response([])

        def deliver_and_wait(requests, **kwargs):
            if requests and requests[0].startswith(
                    ("create-repo:", "create-dist:")):
                # The storage code must tolerate the duplicate creations
                assert kwargs.get("exist_ok")
            batches.append(list(requests))
            if fail_on and requests[0].startswith(fail_on):
                raise RuntimeError("timed out")
            unique = unique_on and requests[0].startswith(unique_on)
            results = []
            for request in requests:
                if request.startswith("create-repo:"):
                    name = request[len("create-repo:"):]
                    existing_repos.add(name)
                    if unique:
                        # Refused as a duplicate, like the real
                        # deliver_and_wait() with exist_ok
                        results.append(None)
                    else:
                        results.append(
                            {"created_resources": ["/repo" + name]})
                elif request.startswith("create-dist:"):
                    existing_dists.add(request[len("create-dist:"):])
                    results.append(None)
                else:
                    results.append(None)
            if unique and not kwargs.get("exist_ok"):
                # Like the real deliver_and_wait() without exist_ok
                raise self._request_error()
            return results

        client.get_repository.side_effect = get_repository
        client.get_distribution.side_effect = get_distribution
        client.deliver_and_wait.side_effect = deliver_and_wait
        client.create_repository.side_effect = \
            lambda name, persistent=False: "create-repo:" + name
        client.create_distribution.side_effect = \
            lambda name, repository, content_guard=None: "create-dist:" + name
        client.publish.side_effect = lambda repository: "publish:" + repository
        client.update_distribution.side_effect = \
            lambda href, **kwargs: "update-dist:" + href
        return batches

    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_batched(self, _mc_redirect):
        storage = self._storage()
        mc_create_dist = Mock()
        storage.client.create_distribution = mc_create_dist
        batches = self._mock_client(storage)
        chroots = ["fedora-40-x86_64", "epel-10-ppc64le"]

        assert storage.init_project("project", chroots) is True

        # All the requests are batched per request type, not per chroot
        assert batches == [
            ["create-repo:owner/project/fedora-40-x86_64",
             "create-repo:owner/project/epel-10-ppc64le"],
            ["create-dist:owner/project/fedora-40-x86_64",
             "create-dist:owner/project/epel-10-ppc64le"],
            ["publish:/repoowner/project/fedora-40-x86_64",
             "publish:/repoowner/project/epel-10-ppc64le"],
        ]

        # The distributions point to the correct repositories, and use the
        # configured content guard
        mc_create_dist.assert_any_call(
            "owner/project/fedora-40-x86_64",
            "/repoowner/project/fedora-40-x86_64",
            content_guard="/guard/1/")
        mc_create_dist.assert_any_call(
            "owner/project/epel-10-ppc64le",
            "/repoowner/project/epel-10-ppc64le",
            content_guard="/guard/1/")

    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_existing_objects_kept(self, _mc_redirect):
        storage = self._storage()
        chroots = ["fedora-40-x86_64", "epel-10-ppc64le"]
        batches = self._mock_client(
            storage,
            existing_repos={"owner/project/fedora-40-x86_64"},
            existing_dists={"owner/project/epel-10-ppc64le"},
        )

        assert storage.init_project("project", chroots) is True

        # Only the missing repository and the missing distribution are
        # created, but both repositories are published
        assert batches == [
            ["create-repo:owner/project/epel-10-ppc64le"],
            ["create-dist:owner/project/fedora-40-x86_64"],
            ["publish:/repoowner/project/fedora-40-x86_64",
             "publish:/repoowner/project/epel-10-ppc64le"],
        ]

    @pytest.mark.parametrize("unique_on", ["create-repo:", "create-dist:"])
    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_unique_error_tolerated(
            self, _mc_redirect, unique_on):
        storage = self._storage()
        chroots = ["fedora-40-x86_64", "epel-10-ppc64le"]
        batches = self._mock_client(storage, unique_on=unique_on)

        # A concurrent action created the same objects in the meantime,
        # and Pulp refuses our duplicate creation
        assert storage.init_project("project", chroots) is True

        # The duplicate creation was tolerated, and the repositories were
        # found by the follow-up query
        assert batches == [
            ["create-repo:owner/project/fedora-40-x86_64",
             "create-repo:owner/project/epel-10-ppc64le"],
            ["create-dist:owner/project/fedora-40-x86_64",
             "create-dist:owner/project/epel-10-ppc64le"],
            ["publish:/repoowner/project/fedora-40-x86_64",
             "publish:/repoowner/project/epel-10-ppc64le"],
        ]

    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_publish_timeout(self, mc_redirect):
        storage = self._storage()
        self._mock_client(storage, fail_on="publish:")

        with pytest.raises(RuntimeError):
            storage.init_project("project", ["fedora-40-x86_64"])

        # The redirect is added even when the publication times out
        mc_redirect.return_value.add.assert_called_once_with(
            "owner", "project")

    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_manual_createrepo_toggle(self, _mc_redirect):
        storage = self._storage()
        batches = self._mock_client(storage)
        storage.client.get_distribution.side_effect = \
            lambda name: self._response([{"pulp_href": "/dist/1/"}])
        mc_update = Mock(
            side_effect=lambda href, **kwargs: "update-dist:" + href)
        storage.client.update_distribution = mc_update

        reason = CreaterepoReason.manual_createrepo_toggle
        assert storage.init_project(
            "project", ["fedora-40-x86_64"], reason=reason) is True

        # The public distribution is pointed back to the repository
        mc_update.assert_called_once_with(
            "/dist/1/", repository="/repoowner/project/fedora-40-x86_64")
        assert batches[-1] == ["publish:/repoowner/project/fedora-40-x86_64"]

    @pytest.mark.parametrize("manual_createrepo", [True, False])
    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_manual_createrepo_event(
            self, _mc_redirect, manual_createrepo):
        storage = self._storage()
        self._mock_client(storage)
        storage.client.get_publication.side_effect = \
            lambda href: self._response([{"pulp_href": "/publication/1/"}])
        publication = "/publication/0/" if manual_createrepo else None
        storage.client.get_distribution.side_effect = \
            lambda name: self._response([
                {"pulp_href": "/dist/1/", "publication": publication}])
        mc_update = Mock(
            side_effect=lambda href, **kwargs: "update-dist:" + href)
        storage.client.update_distribution = mc_update

        reason = CreaterepoReason.manual_createrepo_event
        assert storage.init_project(
            "project", ["fedora-40-x86_64"], reason=reason) is True

        if manual_createrepo:
            # The public distribution is pointed to the same publication
            # as the devel one
            mc_update.assert_called_once_with(
                "/dist/1/", publication="/publication/1/")
        else:
            # The project doesn't use the manual createrepo feature,
            # nothing to update
            storage.client.update_distribution.assert_not_called()

    @patch("copr_backend.storage.PulpHTTPRedirect")
    def test_init_project_devel(self, _mc_redirect):
        storage = self._storage(devel=True)
        batches = self._mock_client(storage)
        storage.client.get_publication.side_effect = \
            lambda href: self._response([{"pulp_href": "/publication/1/"}])
        storage.client.get_distribution.side_effect = \
            lambda name: self._response([{"pulp_href": "/dist/1/"}])
        mc_update = Mock(
            side_effect=lambda href, **kwargs: "update-dist:" + href)
        storage.client.update_distribution = mc_update

        with patch.object(PulpStorage, "wait_for_repo") as mc_wait:
            assert storage.init_project(
                "project", ["fedora-40-x86_64", "epel-10-ppc64le"]) is True

        # We waited for both public repositories to exist
        assert mc_wait.call_count == 2
        mc_wait.assert_any_call(
            "project", "fedora-40-x86_64", "copr_base",
            "https://pulp.fpo/owner/project/fedora-40-x86_64/")

        # Both public distributions were pointed to their publications in
        # one batch
        mc_update.assert_any_call("/dist/1/", publication="/publication/1/")
        assert mc_update.call_count == 2
        assert batches[-2] == ["update-dist:/dist/1/", "update-dist:/dist/1/"]
