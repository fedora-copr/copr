"""
Tests for 'create-chroot'
"""

import pytest
from tests.coprs_test_case import CoprsTestCase
from commands.create_chroot import create_chroot_function

class TestCreateChrootCommand(CoprsTestCase):
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_create_chroot_with_comments(self):
        native = ["fedora-33-x86_64", "fedora-33-i386"]
        emulated = ["fedora-33-ppc64le", "fedora-33-s390x"]
        oldset = set(self.models.MockChroot.query.all())
        create_chroot_function(native)
        create_chroot_function(emulated, branch="fedora/33",
                               comment="Emulated on x86_64")
        newset = set(self.models.MockChroot.query.all())
        new_chroots = newset - oldset
        counter = 0
        for chroot in new_chroots:
            counter += 1
            if chroot.name in emulated:
                assert "Emulated" in chroot.comment
                assert chroot.distgit_branch.name == "fedora/33"
            else:
                assert chroot.comment is None
                assert chroot.distgit_branch.name == "f33"
        assert counter == len(native + emulated)
