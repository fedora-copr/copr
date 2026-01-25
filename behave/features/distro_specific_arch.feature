@architecture_selection
Feature: Building package with arch-specific chroot selection
  Scenario: Build respects ExclusiveArch and ExcludeArch in spec file
    Given a project with "fedora-rawhide, fedora-latest, epel-10" distributions with "x86_64, aarch64, ppc64le, s390x" architectures
    When a build from specfile template "excluded-architectures-hacked.spec" is done
    Then the package "excluded-architectures-hacked" should have "succeeded" state for "fedora-rawhide-x86_64, fedora-latest-aarch64, epel-10-ppc64le" chroots
    Then the package "excluded-architectures-hacked" should have "skipped" state for "fedora-rawhide-ppc64le, fedora-rawhide-aarch64, fedora-rawhide-s390x" chroots
    Then the package "excluded-architectures-hacked" should have "skipped" state for "fedora-latest-x86_64, fedora-latest-ppc64le, fedora-latest-s390x" chroots
    Then the package "excluded-architectures-hacked" should have "skipped" state for "epel-10-x86_64, epel-10-aarch64, epel-10-s390x" chroots
