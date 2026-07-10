import unittest

from copr_rpmbuild.automation.fedora_review import FedoraReview


def _make_task(chroot, fedora_review, package_name="hello"):
    return {
        "chroot": chroot,
        "package_name": package_name,
        "fedora_review": fedora_review,
    }


class TestFedoraReviewEnabled(unittest.TestCase):
    def test_enabled_fedora_chroot_mock_config(self):
        tool = FedoraReview(
            _make_task("fedora-40-x86_64", True), "/resultdir",
            "/mock-config.cfg", None, None)
        self.assertTrue(tool.enabled)

    def test_disabled_review_not_requested(self):
        tool = FedoraReview(
            _make_task("fedora-40-x86_64", False), "/resultdir",
            "/mock-config.cfg", None, None)
        self.assertFalse(tool.enabled)

    def test_disabled_for_non_fedora_chroot(self):
        tool = FedoraReview(
            _make_task("epel-9-x86_64", True), "/resultdir",
            "/mock-config.cfg", None, None)
        self.assertFalse(tool.enabled)

    def test_disabled_without_mock_config_file(self):
        # "direct RPM upload" builds (see rpmbuild/main.py:build_rpm_upload())
        # have no mock build and thus no mock config file -- fedora-review
        # can't run without one, even if fedora_review is requested on a
        # fedora chroot
        tool = FedoraReview(
            _make_task("fedora-40-x86_64", True), "/resultdir",
            None, None, None)
        self.assertFalse(tool.enabled)
