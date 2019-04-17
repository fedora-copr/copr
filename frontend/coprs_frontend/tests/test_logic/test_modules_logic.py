import yaml
from unittest import mock

from tests.coprs_test_case import CoprsTestCase
from coprs.logic.modules_logic import ModuleBuildFacade, ModulemdGenerator

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd


class TestModuleBuildFacade(CoprsTestCase):
    def test_get_build_batches(self):
        pkg1 = Modulemd.ComponentRpm(name="pkg1", rationale="rationale")
        pkg2 = Modulemd.ComponentRpm(name="pkg2", rationale="rationale")
        pkg3 = Modulemd.ComponentRpm(name="pkg3", rationale="rationale", buildorder=1)
        pkg4 = Modulemd.ComponentRpm(name="pkg4", rationale="rationale")
        pkg4.set_buildorder(-20) # https://github.com/fedora-modularity/libmodulemd/issues/77#issuecomment-418198410
        pkg5 = Modulemd.ComponentRpm(name="pkg5", rationale="rationale", buildorder=50)

        # Test trivial usage
        assert ModuleBuildFacade.get_build_batches({}) == []

        # Test multiple components with same buildorder
        rpms = {"pkg1": pkg1, "pkg2": pkg2}
        expected_batches = [{"pkg1": pkg1, "pkg2": pkg2}]
        assert ModuleBuildFacade.get_build_batches(rpms) == expected_batches

        # Test component with buildorder
        rpms = {"pkg3": pkg3, "pkg1": pkg1, "pkg2": pkg2}
        expected_batches = [{"pkg1": pkg1, "pkg2": pkg2}, {"pkg3": pkg3}]
        assert ModuleBuildFacade.get_build_batches(rpms) == expected_batches

        # Test negative buildorder
        rpms = {"pkg1": pkg1, "pkg2": pkg2, "pkg4": pkg4}
        expected_batches = [{"pkg4": pkg4}, {"pkg1": pkg1, "pkg2": pkg2}]
        assert ModuleBuildFacade.get_build_batches(rpms) == expected_batches

        # Test various buildorders at once
        rpms = {"pkg5": pkg5, "pkg3": pkg3, "pkg2": pkg2, "pkg4": pkg4, "pkg1":pkg1}
        expected_batches = [{"pkg4": pkg4}, {"pkg1": pkg1, "pkg2": pkg2}, {"pkg3": pkg3}, {"pkg5": pkg5}]
        assert ModuleBuildFacade.get_build_batches(rpms) == expected_batches

    def test_buildorder_issue_599(self):
        pkg1 = Modulemd.ComponentRpm(name="jss", rationale="JSS packages")
        pkg2 = Modulemd.ComponentRpm(name="tomcatjss", rationale="TomcatJSS packages", buildorder=10)
        pkg3 = Modulemd.ComponentRpm(name="ldapjdk", rationale="LDAP JDK packages", buildorder=10)
        pkg4 = Modulemd.ComponentRpm(name="pki-core", rationale="PKI Core packages", buildorder=20)
        pkg5 = Modulemd.ComponentRpm(name="dogtag-pki", rationale="Dogtag PKI packages", buildorder=20)

        rpms = {"jss": pkg1, "tomcatjss": pkg2, "ldapjdk": pkg3, "pki-core": pkg4, "dogtag-pki": pkg5}
        batches = ModuleBuildFacade.get_build_batches(rpms)

        assert len(batches) == 3
        assert batches[0] == {"jss": pkg1}
        assert batches[1] == {"tomcatjss": pkg2, "ldapjdk": pkg3}
        assert batches[2] == {"pki-core": pkg4, "dogtag-pki": pkg5}


class TestModulemdGenerator(CoprsTestCase):
    config = {"DIST_GIT_URL": "http://distgiturl.org"}

    def test_basic_mmd_attrs(self):
        generator = ModulemdGenerator(name="testmodule", stream="master",
                                      version=123, summary="Some testmodule summary")
        assert generator.mmd.get_name() == "testmodule"
        assert generator.mmd.get_stream() == "master"
        assert generator.mmd.get_version() == 123
        assert generator.mmd.get_summary() == "Some testmodule summary"
        assert generator.nsv == "testmodule-master-123"

    def test_api(self):
        packages = {"foo", "bar", "baz"}
        generator = ModulemdGenerator()
        generator.add_api(packages)
        assert set(generator.mmd.get_rpm_api().get()) == packages

    def test_filter(self):
        packages = {"foo", "bar", "baz"}
        generator = ModulemdGenerator()
        generator.add_filter(packages)
        assert set(generator.mmd.get_rpm_filter().get()) == packages

    def test_profiles(self):
        profile_names = ["default", "debug"]
        profile_pkgs = [["pkg1", "pkg2"], ["pkg3"]]
        profiles = enumerate(zip(profile_names, profile_pkgs))
        generator = ModulemdGenerator()
        generator.add_profiles(profiles)
        assert set(generator.mmd.get_profiles().keys()) == set(profile_names)
        assert set(generator.mmd.get_profiles()["default"].get_rpms().get()) == {"pkg1", "pkg2"}
        assert set(generator.mmd.get_profiles()["debug"].get_rpms().get()) == {"pkg3"}
        assert len(generator.mmd.get_profiles()) == 2

    def test_add_component(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        chroot = self.b1.build_chroots[0]
        generator = ModulemdGenerator(config=self.config)
        generator.add_component(self.b1.package_name, self.b1, chroot,
                                "A reason why package is in the module", buildorder=1)
        assert len(generator.mmd.get_rpm_components()) == 1

        component = generator.mmd.get_rpm_components()[self.b1.package_name]
        assert component.get_buildorder() == 1
        assert component.get_name() == self.b1.package_name
        assert component.get_rationale() == "A reason why package is in the module"

        with mock.patch("coprs.app.config", self.config):
            assert component.get_repository().startswith("http://distgiturl.org")
            assert component.get_repository().endswith(".git")
            assert chroot.dist_git_url.startswith(component.get_repository())
        assert component.get_ref() == chroot.git_hash

    def test_components(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        packages = [self.p1.name, self.p2.name, self.p3.name]
        filter_packages = [self.p1.name, self.p2.name]
        builds = [self.b1.id, self.b3.id]
        generator = ModulemdGenerator(config=self.config)

        with mock.patch("coprs.logic.modules_logic.ModulemdGenerator.add_component") as add_component:
            generator.add_components(packages, filter_packages, builds)
            add_component.assert_called_with(self.p2.name, self.b3, self.b3.build_chroots[-1], mock.ANY, 1)
            assert add_component.call_count == 2

    def test_components_different_chroots(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        # https://bugzilla.redhat.com/show_bug.cgi?id=1444433
        # Test that we can pass a list of builds to the add_components,
        # that have no common chroots
        packages = [self.p1.name, self.p2.name, self.p3.name]
        filter_packages = [self.p1.name, self.p2.name]
        builds = [self.b1.id, self.b3.id]
        generator = ModulemdGenerator(config=self.config)
        generator.add_components(packages, filter_packages, builds)

    def test_add_component_none_build_chroot(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        # https://bugzilla.redhat.com/show_bug.cgi?id=1444433
        generator = ModulemdGenerator(config=self.config)
        generator.add_component(self.p1.name, self.b1, None, "Some reason")

    def test_generate(self):
        generator = ModulemdGenerator("testmodule", "master", 123, "Some testmodule summary", self.config)
        generator.add_api(["foo", "bar", "baz"])
        generator.add_filter(["foo", "bar"])
        yaml.load(generator.generate(), Loader=yaml.BaseLoader)
