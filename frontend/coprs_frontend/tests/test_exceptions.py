import json
import pytest
from werkzeug.exceptions import GatewayTimeout
from tests.coprs_test_case import CoprsTestCase, new_app_context
from coprs import app
from coprs.exceptions import (CoprHttpException,
                              InsufficientStorage,
                              ActionInProgressException)


class TestExceptionHandling(CoprsTestCase):
    def test_json_only_for_api(self):
        app.config["SESSION_COOKIE_DOMAIN"] = "localhost.localdomain"
        r1 = self.tc.get("/nonexisting/endpoint/")
        assert r1.status_code == 404

        with pytest.raises(json.JSONDecodeError):
            json.loads(r1.data)

        r2 = self.tc.get("/api_3/nonexisting/endpoint/")
        assert r2.status_code == 404
        data = json.loads(r2.data)
        assert "error" in data

    def test_both_nonexisting_page_and_object(self):
        r1 = self.tc.get("/nonexisting/endpoint/")
        assert r1.status_code == 404
        assert "<h1> Error 404: Page Not Found</h1>" in str(r1.data)

        r2 = self.tc.get("/coprs/nonexisting/nonexisting/")
        assert r2.status_code == 404

    def test_both_nonexisting_page_and_object_api(self):
        r1 = self.tc.get("/api_3/nonexisting/endpoint/")
        assert r1.status_code == 404
        d1 = json.loads(r1.data)
        assert "API endpoint" in d1["error"]

        r2 = self.tc.get("/api_3/project?ownername=nonexisting&projectname=nonexisting")
        assert r2.status_code == 404
        d2 = json.loads(r2.data)
        assert "Project nonexisting/nonexisting does not exist" in d2["error"]

    def test_api_401(self):
        r1 = self.tc.post("api_3/project/add/someone")
        assert r1.status_code == 401
        data = json.loads(r1.data)
        assert "Login invalid/expired" in data["error"]

    def test_api_403(self, f_users, f_coprs, f_mock_chroots, f_users_api, f_db):
        request_data = {"chroots": None, "description": "Changed description"}
        r1 = self.post_api3_with_auth("api_3/project/edit/user2/foocopr", request_data, self.u3)
        assert r1.status_code == 403
        data = json.loads(r1.data)
        assert "Only owners and admins may update their projects" in data["error"]

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    def test_api_409(self):
        r1 = self.post_api3_with_auth("api_3/build/cancel/1", {}, self.u1)
        assert r1.status_code == 409
        data = json.loads(r1.data)
        assert "Cannot cancel build 1" in data["error"]

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    def test_api_400(self):
        data = {"builder": True}
        url = "api_3/project/permissions/request/user1/foocopr"
        r1 = self.post_api3_with_auth(url, data, self.u1)
        assert r1.status_code == 400
        data = json.loads(r1.data)
        assert "is owner of the 'user1/foocopr' project" in data["error"]

    @new_app_context
    def test_api_504(self):
        def raise_exception():
            raise GatewayTimeout()
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3", follow_redirects=True)
        assert r1.status_code == 504
        data = json.loads(r1.data)
        assert "The API request timeouted" in data["error"]

    @new_app_context
    def test_api_500(self):
        def raise_exception():
            raise CoprHttpException("Whatever unspecified error")
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3", follow_redirects=True)
        assert r1.status_code == 500
        data = json.loads(r1.data)
        assert "Whatever unspecified error" in data["error"]

    @new_app_context
    def test_api_500_default_message(self):
        def raise_exception():
            raise CoprHttpException
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3/", follow_redirects=True)
        assert r1.status_code == 500
        data = json.loads(r1.data)
        assert "Generic copr exception" in data["error"]

    @new_app_context
    def test_api_500_runtime_error(self):
        def raise_exception():
            raise RuntimeError("Whatever unspecified error")
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3", follow_redirects=True)
        assert r1.status_code == 500
        data = json.loads(r1.data)
        assert ("Request wasn't successful, there is probably "
                "a bug in the Copr code.") in data["error"]

    @new_app_context
    def test_api_500_storage(self):
        def raise_exception():
            raise InsufficientStorage
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3", follow_redirects=True)
        assert r1.status_code == 500
        data = json.loads(r1.data)
        assert "Not enough space left" in data["error"]

    @new_app_context
    def test_api_500_in_progress(self):
        def raise_exception():
            raise ActionInProgressException("Hey! Action in progress", None)
        app.view_functions["apiv3_ns.home"] = raise_exception
        r1 = self.tc.get("/api_3", follow_redirects=True)
        assert r1.status_code == 500
        data = json.loads(r1.data)
        assert "Hey! Action in progress" in data["error"]
