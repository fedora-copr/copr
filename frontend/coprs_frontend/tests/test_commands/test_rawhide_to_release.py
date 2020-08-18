"""
Tests for 'branch-fedora' and 'rawhide-to-release'
"""

import pytest

from coprs import db, models
from coprs.logic import coprs_logic
from tests.coprs_test_case import CoprsTestCase, new_app_context
from copr_common.enums import StatusEnum
# pylint: disable=wrong-import-order
from commands.branch_fedora import branch_fedora_function


@pytest.mark.usefixtures("f_copr_chroots_assigned_finished")
class TestBranchFedora(CoprsTestCase):
    @new_app_context
    def test_branch_fedora(self):
        """ Test rawhide-to-release through branch-fedora command """

        # Create one build which is also built in rawhide-i386 chroot
        b_rawhide = models.Build(
            copr=self.c3, copr_dir=self.c3_dir, package=self.p3,
            user=self.u1, submitted_on=50, srpm_url="http://somesrpm",
            source_status=StatusEnum("succeeded"), result_dir='bar')
        db.session.add(b_rawhide)

        for cch in self.c3.copr_chroots:
            print("adding {} buildchroot into {}".format(cch.name, b_rawhide))
            bch_rawhide = models.BuildChroot(
                build=b_rawhide,
                mock_chroot=cch.mock_chroot,
                status=StatusEnum("succeeded"),
                git_hash="12345",
                result_dir='bar',
            )
            bch_rawhide.copr_chroot = cch
            db.session.add(bch_rawhide)

        comment = "test comment to inherit"

        # Create rawhide-x86_64 chroot, and enable it in one project.
        mch_rawhide_x86_64 = models.MockChroot(
            os_release="fedora", os_version="rawhide", arch="x86_64",
            is_active=True, comment=comment)
        mch_rawhide_x86_64.distgit_branch = coprs_logic.BranchesLogic.get_or_create("master")

        cc_rawhide_x86_64 = models.CoprChroot()
        cc_rawhide_x86_64.mock_chroot = mch_rawhide_x86_64
        cc_rawhide_x86_64.copr = self.c1

        db.session.add(mch_rawhide_x86_64)
        db.session.add(cc_rawhide_x86_64)
        db.session.commit()

        assert len(self.c1.copr_chroots) == 2
        assert len(self.c3.copr_chroots) == 2

        branch_fedora_function(19, False, 'f19')

        # check we enabled the rawhide copr_chroots
        assert len(self.c1.copr_chroots) == 3
        assert len(self.c3.copr_chroots) == 3

        # check that x86_64 chroot has no build chroots, and i386 has one
        mchs = coprs_logic.CoprChrootsLogic.mock_chroots_from_names([
            "fedora-19-x86_64",
            "fedora-19-i386",
        ])

        bchs = []
        for mch in mchs:
            # check we inherit the comment
            assert mch.comment == (comment if "x86_64" in mch.name else None)

            for cch in mch.copr_chroots:
                bchs += cch.build_chroots

        assert len(bchs) == 1
        bch = bchs[0]

        assert bch.status == StatusEnum("forked")
        assert bch.build.package == self.p3
