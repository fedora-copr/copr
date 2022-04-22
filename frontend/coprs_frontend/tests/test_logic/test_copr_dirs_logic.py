"""
Tests for CoprDirsLogic
"""

from datetime import datetime, timedelta
import json
import pytest
from coprs import db, models
from tests.coprs_test_case import (
    CoprsTestCase,
    TransactionDecorator,
    new_app_context
)
from commands.delete_dirs import _delete_dirs_function


class TestCoprDirsLogic(CoprsTestCase):
    @TransactionDecorator("u1")
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_users_api", "f_db")
    def test_coprdir_cleanup_no_removal(self):
        self.api3.new_project("test-pr-dirs", ["fedora-17-i386"])
        self.pr_trigger.build_package("test-pr-dirs", "testpkg", 1)
        self.pr_trigger.build_package("test-pr-dirs", "testpkg", 2)
        self.pr_trigger.build_package("test-pr-dirs", "other", 1)
        self.pr_trigger.build_package("test-pr-dirs", "testpkg", 1)
        self.pr_trigger.build_package("test-pr-dirs", "testpkg", 3)
        _delete_dirs_function()
        # nothing got removed
        assert models.Build.query.count() == 5
        assert models.CoprDir.query.count() == 4  # main + 3 PRs

    @TransactionDecorator("u1")
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_users_api", "f_db")
    def test_coprdir_cleanup_no_build(self):
        self.api3.new_project("test-pr-dirs", ["fedora-17-i386"])
        self.pr_trigger.build_package("test-pr-dirs", "testpkg", 1)
        build = models.Build.query.get(1)
        db.session.delete(build)
        models.Action.query.delete()
        db.session.commit()
        assert models.Build.query.count() == 0
        assert models.CoprDir.query.count() == 2
        _delete_dirs_function()
        # nothing got removed
        assert models.Build.query.count() == 0
        assert models.CoprDir.query.count() == 1
        action = models.Action.query.one()
        assert action.action_type == 11
        assert json.loads(action.data) == ["user1/test-pr-dirs:pr:1"]

    @TransactionDecorator("u1")
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_users_api", "f_db")
    def test_coprdir_cleanup_old_pr(self):
        self.api3.new_project("test-pr-dirs", ["fedora-17-i386"])
        old_build_on = datetime.timestamp(datetime.now() - timedelta(days=100))
        self.pr_trigger.build_package_with_args("test-pr-dirs", "testpkg", 1,
                                                old_build_on)
        models.Action.query.delete()
        db.session.commit()
        assert models.Build.query.count() == 1
        assert models.CoprDir.query.count() == 2
        _delete_dirs_function()
        # nothing got removed
        assert models.Build.query.count() == 0
        assert models.CoprDir.query.count() == 1
        action = models.Action.query.one()
        assert action.action_type == 11
        assert json.loads(action.data) == ["user1/test-pr-dirs:pr:1"]

    @TransactionDecorator("u1")
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_users_api", "f_db")
    def test_coprdir_cleanup_one_prs(self):
        self.api3.new_project("test-pr-dirs", ["fedora-17-i386"])
        old_build_on = datetime.timestamp(datetime.now() - timedelta(days=100))
        self.pr_trigger.build_package_with_args("test-pr-dirs", "testpkg", 1,
                                                old_build_on)
        # this assures the pr:1 is kept
        self.pr_trigger.build_package_with_args("test-pr-dirs", "another", 1)
        self.pr_trigger.build_package_with_args("test-pr-dirs", "pr-2-package", 2,
                                                old_build_on)
        self.pr_trigger.build_package_with_args("test-pr-dirs", "pr-3-package", 3,
                                                old_build_on)
        models.Action.query.delete()
        db.session.commit()
        assert models.Build.query.count() == 4
        assert models.CoprDir.query.count() == 4
        _delete_dirs_function()
        # nothing got removed
        assert models.Build.query.count() == 2
        assert models.CoprDir.query.count() == 2
        action = models.Action.query.one()
        assert action.action_type == 11
        assert set(json.loads(action.data)) == set(["user1/test-pr-dirs:pr:2",
                                                    "user1/test-pr-dirs:pr:3"])

    @TransactionDecorator("u1")
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_mock_chroots", "f_users_api", "f_db")
    def test_coprdir_build_normal_then_pr(self):
        chroot = "fedora-17-i386"
        self.api3.new_project("test-pr-dirs", [chroot])
        self.api3.create_distgit_package("test-pr-dirs", "tar", {"webhook_rebuild": True})
        self.api3.rebuild_package("test-pr-dirs", "tar")
        self.backend.finish_build(1, package_name="tar")
        assert models.Build.query.count() == 1

        url = "/backend/get-build-task/1-{}".format(chroot)
        response = self.test_client.get(url)
        assert response.status_code == 200
        result_dict = json.loads(response.data)

        repo_url = "http://copr-dist-git-dev.fedorainfracloud.org/git/user1/{}/tar"
        assert result_dict["git_repo"] == repo_url.format("test-pr-dirs")

        self.pr_trigger.build_package_with_args("test-pr-dirs", "tar", 1)

        url = "/backend/get-build-task/2-{}".format(chroot)
        response = self.test_client.get(url)
        assert response.status_code == 200
        result_dict = json.loads(response.data)
        assert result_dict["git_repo"] == repo_url.format("test-pr-dirs:pr:1")
