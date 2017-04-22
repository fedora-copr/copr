import yaml
from mock import patch, ANY
from tests.coprs_test_case import CoprsTestCase
from coprs.logic.modules_logic import ModulemdGenerator


class TestModulemdGenerator(CoprsTestCase):
    config = {"DIST_GIT_URL": "http://distgiturl.org"}

    def test_basic_mmd_attrs(self):
        generator = ModulemdGenerator("testmodule", "master", 123, "Some testmodule summary", None)
        assert generator.mmd.name == "testmodule"
        assert generator.mmd.stream == "master"
        assert generator.mmd.version == 123
        assert generator.mmd.summary == "Some testmodule summary"

    def test_api(self):
        packages = {"foo", "bar", "baz"}
        generator = ModulemdGenerator()
        generator.add_api(packages)
        assert generator.mmd.api.rpms == packages

    def test_filter(self):
        packages = {"foo", "bar", "baz"}
        generator = ModulemdGenerator()
        generator.add_filter(packages)
        assert generator.mmd.filter.rpms == packages

    def test_profiles(self):
        profile_names = ["default", "debug"]
        profile_pkgs = [["pkg1", "pkg2"], ["pkg3"]]
        profiles = enumerate(zip(profile_names, profile_pkgs))
        generator = ModulemdGenerator()
        generator.add_profiles(profiles)
        assert set(generator.mmd.profiles.keys()) == set(profile_names)
        assert generator.mmd.profiles["default"].rpms == {"pkg1", "pkg2"}
        assert generator.mmd.profiles["debug"].rpms == {"pkg3"}
        assert len(generator.mmd.profiles) == 2

    def test_add_component(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        chroot = self.b1.build_chroots[0]
        generator = ModulemdGenerator(config=self.config)
        generator.add_component(self.b1.package_name, self.b1, chroot,
                                "A reason why package is in the module", buildorder=1)
        assert len(generator.mmd.components.rpms) == 1

        component = generator.mmd.components.rpms[self.b1.package_name]
        assert component.buildorder == 1
        assert component.name == self.b1.package_name
        assert component.rationale == "A reason why package is in the module"

        with patch("coprs.app.config", self.config):
            assert component.repository.startswith("http://distgiturl.org")
            assert component.repository.endswith(".git")
            assert chroot.dist_git_url.startswith(component.repository)
        assert component.ref == chroot.git_hash

    def test_components(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        packages = [self.p1.name, self.p2.name, self.p3.name]
        filter_packages = [self.p1.name, self.p2.name]
        builds = [self.b1.id, self.b3.id]
        generator = ModulemdGenerator(config=self.config)

        with patch("coprs.logic.modules_logic.ModulemdGenerator.add_component") as add_component:
            generator.add_components(packages, filter_packages, builds, chroot=self.mc1.name)
            add_component.assert_called_with(self.p1.name, self.b1, self.b1.build_chroots[0], ANY, 0)
            assert add_component.call_count == 2

    def test_generate(self):
        generator = ModulemdGenerator("testmodule", "master", 123, "Some testmodule summary", self.config)
        generator.add_api(["foo", "bar", "baz"])
        generator.add_filter(["foo", "bar"])
        yaml.load(generator.generate())
