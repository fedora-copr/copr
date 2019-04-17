import json
import pytest
from tests.coprs_test_case import CoprsTestCase
from coprs import app


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
