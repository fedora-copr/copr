"""
Tests for 'branch-fedora' and 'rawhide-to-release'
"""

import json
import pytest

from coprs import db, models
from coprs.logic import coprs_logic
from copr_common.enums import StatusEnum, ActionTypeEnum
# pylint: disable=wrong-import-order
from commands.branch_fedora import branch_fedora_function
from commands.rawhide_to_release import rawhide_to_release_function
from commands.create_chroot import create_chroot_function

from coprs_frontend.tests.coprs_test_case import CoprsTestCase


class TestRawhideToRelease(CoprsTestCase):
    @staticmethod
    @pytest.mark.usefixtures("f_fedora_branching")
    def test_rawhide_to_release_action():
        branchname = "f20"
        create_chroot_function(
            ["fedora-20-i386", "fedora-20-x86_64"],
            branch="f20",
            activated=False,
            comment="some test",
        )
        rawhide_to_release_function(
            "fedora-rawhide-i386",
            "fedora-20-i386",
            False,
        )
        mock_chroots = models.MockChroot.query.filter_by(
            distgit_branch_name=branchname,
        ).all()
        assert len(mock_chroots) == 2
        for mock_chroot in mock_chroots:
            if mock_chroot.name == 'fedora-20-i386':
                assert len(mock_chroot.copr_chroots) == 2
                for build in mock_chroot.builds:
                    assert build.state == 'forked'
            else:
                # nothing in fedora-rawhide-x86_64
                assert len(mock_chroot.copr_chroots) == 0

        actions = models.Action.query.all()
        actions = actions[-2:]
        for action in actions:
            action.appstream_shortcut = json.loads(action.data)["appstream"]
            assert action.appstream_shortcut in [True, False]
        assert actions[0].appstream_shortcut != actions[1].appstream_shortcut


@pytest.mark.usefixtures("f_copr_chroots_assigned_finished", "f_pr_dir",
                         "f_pr_build")
class TestBranchFedora(CoprsTestCase):

    def _get_actions(self):
        actions = self.models.Action.query.all()
        return [ActionTypeEnum(a.action_type) for a in actions]

    def test_branch_fedora(self, capsys):
        """ Test rawhide-to-release through branch-fedora command """

        # Create one build which is also built in rawhide-i386 chroot
        b_rawhide = models.Build(
            copr=self.c3, copr_dir=self.c3_dir, package=self.p3,
            user=self.u1, submitted_on=50, srpm_url="http://somesrpm",
            source_status=StatusEnum("succeeded"), result_dir='bar')
        db.session.add(b_rawhide)

        for cch in self.c3.copr_chroots:
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

        # Build in a custom directory, let's pretend it was in rawhide
        self.bc_pr.mock_chroot = mch_rawhide_x86_64

        db.session.commit()

        assert self._get_actions() == []

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

        assert len(bchs) == 2

        assert bchs[0].status == StatusEnum("forked")
        assert bchs[0].build.package == self.p3

        assert bchs[1].status == StatusEnum("forked")
        assert bchs[1].build.package == self.b_pr.package

        expected_actions = [
            "rawhide_to_release",
            "createrepo",
            "rawhide_to_release",
        ]
        assert self._get_actions() == expected_actions

        # re-run the command, this is no-op
        branch_fedora_function(19, False, 'f19')
        expected_actions += ["createrepo"]
        assert self._get_actions() == expected_actions

        # re-run, and re-fork all the builds, generates new action
        branch_fedora_function(19, True, 'f19')
        expected_actions += [
            "rawhide_to_release",
            "createrepo",
            "rawhide_to_release"
        ]
        assert self._get_actions() == expected_actions

        stdout, _ = capsys.readouterr()
        assert stdout == "\n".join([
            "Handling builds in copr 'user2/barcopr', chroot 'fedora-rawhide-i386'",
            "Processing directory 'user2/barcopr'",
            "  Fresh new build chroots: 1, regenerate 0",
            "Handling builds in copr 'user1/foocopr', chroot 'fedora-rawhide-x86_64'",
            "Processing directory 'user1/foocopr'",
            "Createrepo for 'user1/foocopr', chroot 'fedora-19-x86_64'",
            "Processing directory 'user1/foocopr:PR'",
            "  Fresh new build chroots: 1, regenerate 0",
            "fedora-19-i386 - already exists.",
            "fedora-19-x86_64 - already exists.",
            "Handling builds in copr 'user2/barcopr', chroot 'fedora-rawhide-i386'",
            "Processing directory 'user2/barcopr'",
            "Handling builds in copr 'user1/foocopr', chroot 'fedora-rawhide-x86_64'",
            "Processing directory 'user1/foocopr'",
            "Createrepo for 'user1/foocopr', chroot 'fedora-19-x86_64'",
            "Processing directory 'user1/foocopr:PR'",
            "fedora-19-i386 - already exists.",
            "fedora-19-x86_64 - already exists.",
            "Handling builds in copr 'user2/barcopr', chroot 'fedora-rawhide-i386'",
            "Processing directory 'user2/barcopr'",
            "  Fresh new build chroots: 0, regenerate 1",
            "Handling builds in copr 'user1/foocopr', chroot 'fedora-rawhide-x86_64'",
            "Processing directory 'user1/foocopr'",
            "Createrepo for 'user1/foocopr', chroot 'fedora-19-x86_64'",
            "Processing directory 'user1/foocopr:PR'",
            "  Fresh new build chroots: 0, regenerate 1",
            ""
        ])
