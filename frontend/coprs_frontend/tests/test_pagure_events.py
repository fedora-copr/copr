from pagure_events import event_info_from_pr_comment, event_info_from_push, event_info_from_pr
from tests.coprs_test_case import CoprsTestCase


class TestPagureEvents(CoprsTestCase):
    data = {
        "msg": {
            "agent": "test",
            "pullrequest": {
                "branch": "master",
                "branch_from": "test_PR",
                "id": 1,
                "commit_start": "78a74b02771506daf8927b3391a669cbc32ccf10",
                "commit_stop": "da3d120f2ff24fa730067735c19a0b52c8bc1a44",
                "repo_from": {
                    "fullname": "test/copr/copr",
                    "url_path": "test/copr/copr",
                },
                "project": {
                    "fullname": "test/copr/copr",
                    "url_path": "test/copr/copr",
                },
                'status': 'Open',
                "comments": []
            }
        }
    }
    base_url = "https://pagure.io/"

    def test_negative_event_info_from_pr_comment(self):
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert not event_info

    def test_positive_event_info_from_pr_comment(self):
        self.data['msg']['pullrequest']["comments"].append({"comment": "[copr-build]"})
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert event_info.base_clone_url == "https://pagure.io/test/copr/copr"

    def test_positive_event_info_from_pr(self):
        event_info = event_info_from_pr(self.data, self.base_url)
        assert event_info.base_clone_url == "https://pagure.io/test/copr/copr"

    def test_positive_event_info_from_push(self):
        self.data['msg'] = {
            "branch": "master",
            "start_commit": "61bba3a6bd95fe83c651339018c1d36eae48b620",
            'end_commit': '61bba3a6bd95fe83c651339018c1d36eae48b620',
            "agent": "test"
        }
        self.data['msg']['repo'] = {"fullname": "test", "url_path": "test"}
        event_info = event_info_from_push(self.data, self.base_url)
        assert event_info.base_clone_url == "https://pagure.io/test"
