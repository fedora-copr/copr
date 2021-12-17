@distgit
Feature: Building from external DistGit instances

    Background:
        Given a project that builds packages for this system

    @builds
    Scenario: Test that dist-git builds work
        When a build of Fedora DistGit hello package from rawhide branch is done
        Then the build results are distributed

    @packages
    Scenario: Test that we can edit dist-git packages
        When a DistGit CentOS "tar" package from branch "c7" is added
        And the DistGit package is modified to build from branch "c8"
        Then the package is configured to build from distgit branch "c8"

    @packages @builds
    Scenario: Test that we can add and build dist-git packages
        When a DistGit CentOS "filesystem" package from branch "c8" is added
        And the package build is requested
        Then the build results are distributed

    @packages @builds @centos_stream
    Scenario: Test that we can build from CentOS Stream dist-git
        When a DistGit CentOS-Stream "filesystem" package from branch "c9s" is added
        And the package build is requested
        Then the build results are distributed

    @builds
    Scenario: Test that dist-git builds from forks work
        When build of Fedora DistGit namespaced hello package from rawhide branch in forks/frostyx is done
        Then the build results are distributed
