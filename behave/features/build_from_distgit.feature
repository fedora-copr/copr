@distgit
Feature: Building from external DistGit instances

    Background:
        Given a project that builds packages for this system

    @builds
    Scenario: Test that dist-git builds work
        When a build of Fedora DistGit hello package from master branch is done
        Then the build results are distributed

    @packages
    Scenario: Test that we can edit dist-git packages
        When a DistGit CentOS "tar" package from branch "c7" is added
        And the DistGit package is modified to build from branch "c8"
        Then the package is configured to build from distgit branch "c8"

    @packages @builds
    Scenario: Test that we can add and build dist-git packages
        When a DistGit CentOS "setup" package from branch "c8" is added
        And the package build is requested
        Then the build results are distributed
