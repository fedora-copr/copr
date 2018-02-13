import yaml
from munch import Munch
from mock import patch, ANY
from tests.coprs_test_case import CoprsTestCase
from coprs.logic.modules_logic import ModuleBuildFacade, ModulemdGenerator, MBSResponse, MBSProxy
from modulemd.components.rpm import ModuleComponentRPM


class TestModuleBuildFacade(CoprsTestCase):
    def test_get_build_batches(self):
        pkg1 = ModuleComponentRPM("pkg1", "rationale")
        pkg2 = ModuleComponentRPM("pkg2", "rationale")
        pkg3 = ModuleComponentRPM("pkg3", "rationale", buildorder=1)
        pkg4 = ModuleComponentRPM("pkg4", "rationale", buildorder=-20)
        pkg5 = ModuleComponentRPM("pkg5", "rationale", buildorder=50)

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


class TestModulemdGenerator(CoprsTestCase):
    config = {"DIST_GIT_URL": "http://distgiturl.org"}

    def test_basic_mmd_attrs(self):
        generator = ModulemdGenerator("testmodule", "master", 123, "Some testmodule summary", None)
        assert generator.mmd.name == "testmodule"
        assert generator.mmd.stream == "master"
        assert generator.mmd.version == 123
        assert generator.mmd.summary == "Some testmodule summary"
        assert generator.nsv == "testmodule-master-123"

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
            generator.add_components(packages, filter_packages, builds)
            add_component.assert_called_with(self.p2.name, self.b3, self.b3.build_chroots[-1], ANY, 1)
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
        yaml.load(generator.generate())


class TestMBSResponse(CoprsTestCase):
    def test_status(self):
        assert MBSResponse(Munch(status_code=500)).failed is True
        assert MBSResponse(Munch(status_code=409)).failed is True
        assert MBSResponse(Munch(status_code=201)).failed is False

    def test_message(self):
        req1 = Munch(status_code=500, reason="foo reason")
        res1 = MBSResponse(req1)
        assert res1.message == "Error from MBS: 500 - foo reason"

        req2 = Munch(status_code=409, content='{"message": "foo message"}')
        res2 = MBSResponse(req2)
        assert res2.message == "Error from MBS: foo message"

        con3 = '{"name": "testmodule", "stream": "master", "version": 123}'
        req3 = Munch(status_code=201, content=con3)
        res3 = MBSResponse(req3)
        assert res3.message == "Created module testmodule-master-123"


class TestMBSProxy(CoprsTestCase):

    @patch("requests.post")
    def test_post(self, post_mock):
        url = "http://some-module-build-service.org"
        proxy = MBSProxy(url)
        response = proxy.post(None, None, None)
        post_mock.assert_called()
        args, kwargs = post_mock.call_args
        assert args[0] == url
        assert isinstance(response, MBSResponse)
