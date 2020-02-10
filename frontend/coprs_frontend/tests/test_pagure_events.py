from pagure_events import (event_info_from_pr_comment, event_info_from_push, event_info_from_pr, ScmPackage,
                           build_on_fedmsg_loop, ScmPackage)
from tests.coprs_test_case import CoprsTestCase
from unittest import mock


class Message:
    def __init__(self, topic, body):
        self.topic = topic
        self.body = body


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

    def test_negative_is_dir_in_commit(self, f_users, f_coprs):
        self.p2 = self.models.Package(
            copr=self.c1, copr_dir=self.c1_dir, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test"}'
        )
        candidates = ScmPackage.get_candidates_for_rebuild("https://pagure.io/test")
        dir_in_commit = [pkg for pkg in candidates if pkg.is_dir_in_commit({''})]

        assert len(dir_in_commit) == 0

    def test_positive_is_dir_in_commit(self, f_users, f_coprs):
        dir_in_commit = False
        changed_files = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        self.p2 = self.models.Package(
            copr=self.c1, copr_dir=self.c1_dir, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test"}'
        )
        candidates = ScmPackage.get_candidates_for_rebuild("https://pagure.io/test")
        for pkg in candidates:
            dir_in_commit = pkg.is_dir_in_commit(changed_files)

        assert dir_in_commit is True

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly')
    def test_positive_build_from_pr_update(self, f_get_repeatedly, f_raw_commit_changes, f_users, f_coprs):
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        self.p1 = self.models.Package(
            copr=self.c1, copr_dir=self.c1_dir, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test/copr/copr"}'
        )
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.pull-request.updated',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 1
        assert builds[0].scm_object_type == 'pull-request'

    def test_negative_event_info_from_pr_comment_random_comment(self):
        self.data['msg']['pullrequest']["comments"].append({"comment": "my testing comment"})
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert event_info is False

    def test_positive_event_info_from_pr_comment(self):
        self.data['msg']['pullrequest']["comments"].append({"comment": "[copr-build]"})
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert event_info.base_clone_url == "https://pagure.io/test/copr/copr"

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly')
    def test_negative_build_from_pr_comment(self, f_get_repeatedly, f_raw_commit_changes, f_users, f_coprs):
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.pull-request.comment.added',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 0

    def test_negative_event_info(self, f_users, f_coprs):
        self.data['msg']['pullrequest']["status"] = "Closed"
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.pull-request.comment.added',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 0

    def test_negative_event_info_from_pr_comment_closed_pr(self):
        self.data['msg']['pullrequest']["status"] = "Closed"
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert event_info is False

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

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly')
    def test_positive_build_from_push(self, f_get_repeatedly, f_raw_commit_changes, f_users, f_coprs):
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        self.p1 = self.models.Package(
            copr=self.c1, copr_dir=self.c1_dir, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test"}'
        )
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.git.receive',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 1
        assert builds[0].scm_object_type == 'commit'

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly')
    def test_negative_build_from_push(self, f_get_repeatedly, f_raw_commit_changes, f_users, f_coprs):
        f_raw_commit_changes.return_value = {''}
        self.p1 = self.models.Package(
            copr=self.c1, copr_dir=self.c1_dir, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test"}',
        )
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.git.receive',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 0

    def test_negative_unknown_topic(self):
        build = build_on_fedmsg_loop()
        message = Message(
            'io.pagure.prod.pagure.git.test',
            self.data['msg']
        )
        build(message)
        builds = self.models.Build.query.all()
        assert len(builds) == 0
