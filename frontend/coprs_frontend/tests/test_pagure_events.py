from unittest import mock
import pytest
from pagure_events import (event_info_from_pr_comment, event_info_from_push,
                           event_info_from_pr, ScmPackage, build_on_fedmsg_loop,
                           TOPICS)
from tests.lib.pagure_pull_requests import get_pagure_pr_event
from tests.coprs_test_case import CoprsTestCase


class Message:
    def __init__(self, topic, body):
        self.topic = topic
        self.body = body


class TestPagureEvents(CoprsTestCase):
    def setup_method(self, method):
        super().setup_method(method)
        # pylint: disable=attribute-defined-outside-init
        self.data = get_pagure_pr_event()
        self.base_url = "https://pagure.io/"

    def _setup_push_msg(self):
        self.data['msg'] = {
            "branch": "master",
            "start_commit": "61bba3a6bd95fe83c651339018c1d36eae48b620",
            'end_commit': '61bba3a6bd95fe83c651339018c1d36eae48b620',
            "agent": "test",
            "repo": {"fullname": "test", "url_path": "test"},
        }

    def test_negative_event_info_from_pr_comment(self):
        event_info = event_info_from_pr_comment(self.data, self.base_url)
        assert not event_info

    def test_negative_is_dir_in_commit(self, f_users, f_coprs):
        self.p2 = self.models.Package(
            copr=self.c1, name="hello-world", source_type=8, webhook_rebuild=True,
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
            copr=self.c1, name="hello-world", source_type=8, webhook_rebuild=True,
            source_json='{"clone_url": "https://pagure.io/test"}'
        )
        candidates = ScmPackage.get_candidates_for_rebuild("https://pagure.io/test")
        for pkg in candidates:
            dir_in_commit = pkg.is_dir_in_commit(changed_files)

        assert dir_in_commit is True

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly', mock.Mock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots")
    def test_positive_build_from_pr_update(self, f_raw_commit_changes):
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        self.p1 = self.models.Package(
            copr=self.c1, name="hello-world", source_type=8, webhook_rebuild=True,
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
        assert event_info.user == "jdoe"

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
        assert event_info.user == "test"

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly', mock.Mock())
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots")
    def test_positive_build_from_push(self, f_raw_commit_changes):
        self._setup_push_msg()
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
        self.p1 = self.models.Package(
            copr=self.c1, name="hello-world", source_type=8, webhook_rebuild=True,
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
        self._setup_push_msg()
        f_raw_commit_changes.return_value = {''}
        self.p1 = self.models.Package(
            copr=self.c1, name="hello-world", source_type=8, webhook_rebuild=True,
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

    @mock.patch('pagure_events.helpers.raw_commit_changes')
    @mock.patch('pagure_events.get_repeatedly', mock.Mock())
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs", "f_mock_chroots")
    def test_positive_build_from_pr_fork(self, f_raw_commit_changes):
        """
        Make sure that PRs against forks in Fedora DistGit trigger builds
        """
        f_raw_commit_changes.return_value = {
            'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
            'tests/integration/conftest.py b/tests/integration/conftest.py index '
            '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}

        # Create a new package via API instead of simply SQLAlchemy model, so
        # we can make sure that the clone URL is generated properly
        endpoint = "/api_3/package/add/{0}/{1}/{2}".format(
            self.c1.full_name, "hello-world", "distgit")
        form_data = {
            'package_name': 'hello-world',
            'distgit': 'fedora',
            'namespace': 'forks/frostyx',
            'webhook_rebuild': True,
        }
        response = self.post_api3_with_auth(endpoint, form_data, self.u1)
        assert response.status_code == 200

        # Adjust recognized message topics to support Fedora DistGit
        event = "org.fedoraproject.prod.pagure.pull-request.updated"
        url = "https://src.fedoraproject.org/"
        TOPICS[event] = url

        # Fake a Fedora DistGit PR message
        paths = {
            "fullname": "forks/frostyx/rpms/hello-world",
            "url_path": "forks/frostyx/rpms/hello-world",
        }
        self.data["msg"]["pullrequest"]["project"].update(paths)
        self.data["msg"]["pullrequest"]["repo_from"].update(paths)
        message = Message(event, self.data['msg'])

        build = build_on_fedmsg_loop()
        build(message)
        builds = self.models.Build.query.all()

        # Make sure a build was created
        assert len(builds) == 1
        assert builds[0].scm_object_type == 'pull-request'
