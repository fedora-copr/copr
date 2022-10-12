from coprs import app
from coprs.auth import FedoraAccounts
from tests.coprs_test_case import CoprsTestCase


class TestMisc(CoprsTestCase):
    def test_fed_raw_name(self):
        providers = [
            "https://id.fedoraproject.org/",
            "https://id.fedoraproject.org",
        ]
        for provider in providers:
            app.config["OPENID_PROVIDER_URL"] = provider
            fullname = "https://someuser.id.fedoraproject.org/"
            assert FedoraAccounts.fed_raw_name(fullname) == "someuser"

    def test_fed_raw_name_scheme(self):
        app.config["OPENID_PROVIDER_URL"] = "foo://id.fedoraproject.org/"
        fullname = "bar://someuser.id.fedoraproject.org/"
        assert FedoraAccounts.fed_raw_name(fullname) == "someuser"

    def test_fed_raw_name_without_oid_url(self):
        assert FedoraAccounts.fed_raw_name("someuser") == "someuser"
