import json
from tests.coprs_test_case import CoprsTestCase


class TestMockChroot(CoprsTestCase):

    def test_list_available_chroots(self, f_mock_chroots):
        r = self.tc.get("/api_3/mock-chroots/list")
        assert r.status_code == 200
        assert json.loads(r.data) == {
            "fedora-18-x86_64": "",
            "fedora-17-x86_64": "A short chroot comment",
            "fedora-17-i386": "Chroot comment containing [url with four\nwords](https://copr.fedorainfracloud.org/)",
            "fedora-rawhide-i386": "",
        }
