from coprs.logic.packages_logic import PackagesLogic

from tests.coprs_test_case import CoprsTestCase


class TestPackagesLogic(CoprsTestCase):

    def test_last_successful_build_chroots(self, f_users, f_fork_prepare, f_build_few_chroots):
        builds_p4 = PackagesLogic.last_successful_build_chroots(self.p4)
        builds_p5 = PackagesLogic.last_successful_build_chroots(self.p5)
        assert builds_p4 == {self.b6: self.b6_bc}
        assert builds_p5 == {self.b10: [self.b10_bc[0]],
                             self.b11: [self.b11_bc[1]]}
