"""
Test routes related to DistGit method
"""
import json
import pytest

from copr_common.enums import BuildSourceEnum

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator

class TestDistGitMethod(CoprsTestCase):
    """ add/edit package, add build """

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_copr_user_can_add_distgit_build(self):
        """ add build using web-UI """
        self.db.session.add_all([self.u1, self.c1])
        data = {
            "package_name": "mock",
            "committish": "master",
            "chroots": ["fedora-18-x86_64"],
        }
        endpoint = "/coprs/{0}/{1}/new_build_distgit/".format(self.u1.name,
                                                              self.c1.name)
        self.test_client.post(endpoint, data=data, follow_redirects=True)
        build = self.models.Build.query.first()
        assert build.source_type == BuildSourceEnum.distgit
        assert build.source_json == json.dumps({
            "clone_url": "https://src.fedoraproject.org/rpms/mock",
            "committish": "master"})

        assert len(build.chroots) == 1
        assert build.chroots[0].name == "fedora-18-x86_64"

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_copr_user_can_add_distgit_package(self):
        """ add package using web-UI """
        self.db.session.add_all([self.u1, self.c1])
        data = {
            "package_name": "mock",
            "distgit": "fedora",
            "committish": "master",
        }
        endpoint = "/coprs/{0}/{1}/package/new/distgit".format(self.u1.name,
                                                               self.c1.name)
        self.test_client.post(endpoint, data=data, follow_redirects=True)

        package = self.models.Package.query.first()
        assert package.name == "mock"
        assert package.source_type == 10
        assert json.loads(package.source_json) == {
            "distgit": "fedora",  # prefilled as default
            "committish": "master",
            "clone_url": "https://src.fedoraproject.org/rpms/mock"
        }

        self.db.session.close()
        self.db.session.add_all([self.u1, self.c1])
        endpoint = "/coprs/{0}/{1}/package/mock/edit/distgit".format(self.u1.name,
                                                                     self.c1.name)
        data["committish"] = "f15"
        data["namespace"] = "forks/user1"
        self.test_client.post(endpoint, data=data, follow_redirects=True)

        package = self.models.Package.query.first()
        assert package.name == "mock"
        assert package.source_type == 10
        assert json.loads(package.source_json) == {
            "distgit": "fedora",  # prefilled as default
            "committish": "f15",
            "namespace": "forks/user1",
            "clone_url": "https://src.fedoraproject.org/forks/user1/rpms/mock"
        }
