import yaml
from unittest import mock

from tests.coprs_test_case import CoprsTestCase
from coprs.logic.modules_logic import ModuleBuildFacade, ModulemdGenerator
from coprs.logic.coprs_logic import CoprChrootsLogic
from copr_common.enums import ActionTypeEnum, BackendResultEnum, ModuleStatusEnum, StatusEnum
from coprs import models, db

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd


class TestModulesLogic(CoprsTestCase):
    def test_state(self, f_users, f_coprs, f_mock_chroots, f_builds, f_modules, f_db):
        self.b1.build_chroots[0].status = StatusEnum("pending")
        self.b3.build_chroots[0].status = StatusEnum("succeeded")
        self.b3.build_chroots[1].status = StatusEnum("succeeded")
        self.b3.source_status = StatusEnum("succeeded")

        # even though b3 is succeeded, b1 is still pending
        self.m1.builds = [self.b1, self.b3]
        assert self.m1.status == ModuleStatusEnum("pending")

        # now what if b1 succeeds
        self.b1.build_chroots[0].status = StatusEnum("succeeded")
        assert self.m1.status == ModuleStatusEnum("succeeded")

        # let's say that b3 failed
        self.b3.build_chroots[0].status = StatusEnum("failed")
        assert self.m1.status == ModuleStatusEnum("failed")


        # once the action exists, it dictates the status
        self.b3.build_chroots[0].status = StatusEnum("succeeded")
        action = models.Action(
            action_type=ActionTypeEnum("build_module"),
            object_type="module",
            object_id=self.m1.id,
        )
        db.session.add(action)
        assert self.m1.status == ModuleStatusEnum("waiting")

        # the backend proceeds the action
        action.result = BackendResultEnum("success")
        assert self.m1.status == ModuleStatusEnum("succeeded")


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

    def test_add_builds_batches(self, f_users, f_coprs, f_mock_chroots, f_builds, f_modules, f_db):
        pkg1 = Modulemd.ComponentRpm(name="foo", rationale="foo package")
        pkg2 = Modulemd.ComponentRpm(name="bar", rationale="bar package", buildorder=10)
        pkg3 = Modulemd.ComponentRpm(name="baz", rationale="baz package", buildorder=10)

        generator = ModulemdGenerator(name="testmodule", stream="master", version=123, summary="some summary")
        facade = ModuleBuildFacade(self.u1, self.c1, generator.generate(), "testmodule.yaml")
        facade.add_builds({"foo": pkg1, "bar": pkg2, "baz": pkg3}, self.m1)

        b1, b2, b3 = self.m1.builds
        assert b1.batch != b2.batch == b3.batch
        assert b2.batch.blocked_by == b1.batch

    def test_platform_chroots(self, f_users, f_coprs, f_mock_chroots_many, f_builds, f_modules, f_db):
        fedora_chroots = [chroot.name for chroot in self.c1.mock_chroots if chroot.name.startswith("fedora")]

        # Test excluding platform chroots
        CoprChrootsLogic.update_from_names(self.u1, self.c1, fedora_chroots)
        generator = ModulemdGenerator(name="testmodule", stream="master", version=123, summary="some summary")
        generator.mmd.set_buildrequires({"platform": "-f22"})
        facade = ModuleBuildFacade(self.u1, self.c1, generator.generate(), "testmodule.yaml")
        assert {chroot.name for chroot in self.c1.active_chroots} == set(fedora_chroots)
        assert ("fedora-22-i386" not in facade.platform_chroots) and ("fedora-22-x86_64" in fedora_chroots)
        assert ("fedora-22-x86_64" not in facade.platform_chroots) and ("fedora-22-x86_64" in fedora_chroots)

        # Test setting platform chroots from scratch
        CoprChrootsLogic.update_from_names(self.u1, self.c1, fedora_chroots)
        generator = ModulemdGenerator(name="testmodule", stream="master", version=123, summary="some summary")
        generator.mmd.set_buildrequires({"platform": "f22"})
        facade = ModuleBuildFacade(self.u1, self.c1, generator.generate(), "testmodule.yaml")
        assert {chroot.name for chroot in self.c1.active_chroots} == set(fedora_chroots)
        assert set(facade.platform_chroots) == {"fedora-22-i386", "fedora-22-x86_64"}


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
        assert set(generator.mmd.get_profiles()["default"].peek_rpms().get()) == {"pkg1", "pkg2"}
        assert set(generator.mmd.get_profiles()["debug"].peek_rpms().get()) == {"pkg3"}
        assert len(generator.mmd.get_profiles()) == 2

    def test_add_component(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        chroot = self.b1.build_chroots[0]
        generator = ModulemdGenerator(config=self.config)
        generator.add_component(self.b1.package_name, self.b1, chroot,
                                "A reason why package is in the module", buildorder=1)
        assert len(generator.mmd.get_rpm_components()) == 1

        component = generator.mmd.get_rpm_components()[self.b1.package_name]
        assert component.get_buildorder() == 1
        assert component.peek_name() == self.b1.package_name
        assert component.peek_rationale() == "A reason why package is in the module"

        with mock.patch("coprs.app.config", self.config):
            assert component.peek_repository().startswith("http://distgiturl.org")
            assert component.peek_repository().endswith(".git")
            assert chroot.dist_git_url.startswith(component.peek_repository())
        assert component.peek_ref() == chroot.git_hash

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
