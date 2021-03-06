from coprs import app
from coprs.views.misc import fed_raw_name
from tests.coprs_test_case import CoprsTestCase


class TestMisc(CoprsTestCase):
    def test_fed_raw_name(self):
        providers = [
            "https://id.fedoraproject.org/",
            "https://id.fedoraproject.org",
        ]
        for provider in providers:
            app.config["OPENID_PROVIDER_URL"] = provider
            assert fed_raw_name("https://someuser.id.fedoraproject.org/") == "someuser"

    def test_fed_raw_name_scheme(self):
        app.config["OPENID_PROVIDER_URL"] = "foo://id.fedoraproject.org/"
        assert fed_raw_name("bar://someuser.id.fedoraproject.org/") == "someuser"

    def test_fed_raw_name_without_oid_url(self):
        assert fed_raw_name("someuser") == "someuser"
