@autospec
Feature: Building from DistGit with %autospec

    Background:
        Given a project with fedora-rawhide-x86_64 chroot enabled

        Scenario: Test that autospec macros are expanded
            When a build of Fedora DistGit python-copr-common package from private-autospec branch is done
            Then there's a package python-copr-common build with source version-release 0.13.1-3 (without dist tag)
            # https://src.fedoraproject.org/rpms/python-copr-common/c/1b1152f6a8affac8ad0bd58312fb596ace2bd4f3?branch=private-autospec
            Then package changelog for python-copr-common in fedora-rawhide-x86_64 chroot contains "And try to bump to Release: 3" string
