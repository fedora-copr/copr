@rpm_upload
Feature: Direct RPM upload

    Users can upload already-built RPM(s) directly for a single chroot.

    Background:
        Given a project that builds packages for this system

    @builds
    Scenario: Test that a directly uploaded RPM ends up in the repository
        When a locally built "copr-rpm-upload-sanity-test" RPM is uploaded directly to the project
        Then the uploaded RPM "copr-rpm-upload-sanity-test" is present in the repository
