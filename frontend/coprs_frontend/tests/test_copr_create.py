""" Test API/WebUI project craeate operations """

import pytest
from tests.coprs_test_case import (CoprsTestCase, TransactionDecorator)
from tests.request_test_api import parse_web_form_error

class TestProjectCreate(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    @pytest.mark.parametrize("kind", ["homepage", "contact"])
    def test_invalid_contact(self, request_type, kind):
        client = self.api3 if request_type == "api" else self.web_ui
        client.success_expected = False
        kwargs = {kind: "invalidvalue"}
        result = client.new_project("test-isolation", ["fedora-rawhide-i386"],
                                    **kwargs)

        if kind == "homepage":
            expected = "Invalid URL"
        else:
            expected = "Contact must be email address or URL"

        if client == self.api3:
            assert expected in result.json["error"]
        else:
            error = parse_web_form_error(result.data)
            assert len(error) == 1
            assert expected in error[0]

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    @pytest.mark.parametrize("kind", ["homepage", "contact"])
    def test_valid_contact(self, request_type, kind):
        client = self.api3 if request_type == "api" else self.web_ui

        if kind == "homepage":
            values = ["http://example.com"]
        else:
            values = ["tester@example.com", "https://example.com"]

        i = 0
        for value in values:
            kwargs = {kind: value}
            client.new_project("test-isolation-{}".format(i), ["fedora-rawhide-i386"],
                               **kwargs)
            i = i+1
