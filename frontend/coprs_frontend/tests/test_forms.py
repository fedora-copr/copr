import re
import pytest
import flask
from tests.coprs_test_case import CoprsTestCase
from coprs import app
from coprs.forms import (
    PinnedCoprsForm,
    CoprFormFactory,
    CreateModuleForm,
    REGEX_BOOTSTRAP_IMAGE,
    REGEX_CHROOT_DENYLIST,
)


class TestCoprsFormFactory(CoprsTestCase):

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_empty_chroots(self):
        with app.app_context():
            flask.g.user = self.u2
            form = CoprFormFactory.create_form_cls()(name="foo")
            assert not form.validate()
            assert "At least one chroot" in form.errors[None][0]


class TestPinnedCoprsForm(CoprsTestCase):

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_limit(self):
        app.config["PINNED_PROJECTS_LIMIT"] = 1
        with app.app_context():
            flask.g.user = self.u2

            form = PinnedCoprsForm(self.u2, copr_ids=["2"])
            assert form.validate()

            form = PinnedCoprsForm(self.u2, copr_ids=["2", "3"])
            assert not form.validate()
            assert "Too many" in form.errors["copr_ids"][0]

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_unique_coprs(self):
        app.config["PINNED_PROJECTS_LIMIT"] = 2
        with app.app_context():
            flask.g.user = self.u2
            form = PinnedCoprsForm(self.u2, copr_ids=["2", "2"])
            assert not form.validate()
            assert "only once" in form.errors["copr_ids"][0]

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_db")
    def test_invalid_choice(self):
        app.config["PINNED_PROJECTS_LIMIT"] = 2
        with app.app_context():
            flask.g.user = self.u2
            form = PinnedCoprsForm(self.u2, copr_ids=["1"])
            assert not form.validate()
            assert "Unexpected value selected" in form.errors["copr_ids"][0]


class TestCreateModuleForm(CoprsTestCase):

    def test_successful_validate(self):
        with app.test_request_context():
            flask.request.form = {
                "profile_names-0": "foo",
                "profile_names-1": "bar",
            }
            form = CreateModuleForm(filter=["pkg1"],
                                    profile_names=["foo", "bar"])
            assert not form.validate()
            assert "components" in form.errors
            assert "You must select some packages" \
                in form.errors["components"][0]

            form = CreateModuleForm(components=["pkg1"],
                                    profile_names=["foo", "bar"])
            assert form.validate()

    def test_unique_names(self):
        with app.test_request_context():
            flask.request.form = {
                "profile_names-0": "foo",
                "profile_names-1": "foo",
            }
            form = CreateModuleForm(components=["pkg1"],
                                    profile_names=["foo", "foo"])
            assert not form.validate()
            assert "Profile names must be unique" in \
                form.errors["profile_names"][0]

    @staticmethod
    def test_profile_name_required():
        with app.test_request_context():
            flask.request.form = {
                "profile_names-0": "foo",
                "profile_names-1": "",
                "profile_pkgs-1-0": "pkg1",
                "profile_pkgs-1-1": "pkg2",
            }
            form = CreateModuleForm(components=["pkg1"],
                                    profile_names=["foo", "bar"])
            assert not form.validate()
            assert "Missing profile name" in form.errors["profile_names"][0]


def test_form_regexes():
    assert re.match(REGEX_BOOTSTRAP_IMAGE, "fedora:33")
    assert re.match(REGEX_BOOTSTRAP_IMAGE, "fedora")
    assert re.match(REGEX_BOOTSTRAP_IMAGE, "registry.fedoraproject.org/fedora:rawhide")
    assert re.match(REGEX_BOOTSTRAP_IMAGE, "registry.fedoraproject.org/fedora")
    assert not re.match(REGEX_BOOTSTRAP_IMAGE, "docker://example.com/test:30")

    items = [
        "fedora",
        "fedora-*-x86_64",
        "fedora-*-*",
        "fedora-39-x86_64",
        "fedora-rawhide-aarch64",
        "amazonlinux-2023-aarch64",
        "centos-stream+epel-next-9-x86_64",
        "openeuler-22.03-x86_64",
        "opensuse-leap-15.4-x86_64",
        "opensuse-leap-15.4-x86_64",
    ]
    for item in items:
        assert re.match(REGEX_CHROOT_DENYLIST, item)

    for item in ["fe|ora", "#fedora", "fedora/39", "fedora:39"]:
        assert not re.match(REGEX_CHROOT_DENYLIST, item)
