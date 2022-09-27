import pytest

from coprs.logic.packages_logic import PackagesLogic

from tests.coprs_test_case import CoprsTestCase


class TestPackagesLogic(CoprsTestCase):

    def test_last_successful_build_chroots(self, f_users, f_fork_prepare, f_build_few_chroots):
        builds_p4 = PackagesLogic.last_successful_build_chroots(self.p4)
        builds_p5 = PackagesLogic.last_successful_build_chroots(self.p5)
        assert builds_p4 == {self.b6: self.b6_bc}
        assert builds_p5 == {self.b10: [self.b10_bc[0]],
                             self.b11: [self.b11_bc[1]]}

    @staticmethod
    @pytest.mark.parametrize(
        "ref, copr_pkg_name, result",
        [
            pytest.param("copr-cli-1-1alpha", "copr-cli", True),
            pytest.param("copr-cli-1", "copr-cli", True),
            pytest.param("copr-cli-1", "copr", False),
            pytest.param("copr_cli-1.1-1", "copr_cli", True),
            pytest.param("copr_cli-1.1", "copr_cli", True),
            pytest.param("copr-frontend-a1", "copr", False),
            pytest.param("copr-frontend-a1", "copr-frontend", True),
            pytest.param("copr_frontend_a1", "copr-frontend", True),
            pytest.param("copr-frontend-a1", "copr_frontend", True),
            pytest.param("copr_frontend_a1", "copr_frontend", True),
            pytest.param("copr_frontend-a1", "copr-frontend", False),
            pytest.param("copr-1.1alpha-1", "copr", True),
            pytest.param("copr-1.1alpha-1beta", "copr", True),
            pytest.param("copr-1.1-1", "copr", True),
            pytest.param("copr-1", "copr", True),
        ]
    )
    def test_ref_matches_copr_pkgname(ref, copr_pkg_name, result):
        # pylint: disable-next=protected-access
        assert PackagesLogic._ref_matches_copr_pkgname(ref, copr_pkg_name) == result
