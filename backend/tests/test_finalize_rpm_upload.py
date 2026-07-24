# pylint: disable=attribute-defined-outside-init
import json
import logging
import os
import shutil
import tempfile
from unittest import mock

from munch import Munch

from copr_common.enums import ActionTypeEnum, BackendResultEnum, StatusEnum

from copr_backend.actions import Action
from copr_backend.exceptions import CoprSignError


class TestFinalizeRpmUpload:
    def setup_method(self, _method):
        self.tmp_dir = tempfile.mkdtemp(prefix="copr-test-finalize-rpm-upload")
        self.log = logging.getLogger("test-finalize-rpm-upload")

        self.opts = Munch(
            destdir=self.tmp_dir,
            frontend_base_url="https://example.com",
            frontend_auth="foobar",
            results_baseurl="http://example.com/results",
            do_sign=False,
        )
        self.ext_data = {
            "ownername": "foo",
            "projectname": "bar",
            "project_dirname": "bar",
            "appstream": True,
            "storage": 0,  # StorageEnum.backend
            "devel": False,
            "persistent": False,
            "build_id": 42,
            "chroot": "fedora-40-x86_64",
            "file_urls": ["https://example.com/tmp/abc/hello-2.8-1.fc40.x86_64.rpm"],
        }
        self.nevra = {
            "name": "hello", "epoch": None, "version": "2.8",
            "release": "1.fc40", "arch": "x86_64",
        }

    def teardown_method(self, _method):
        shutil.rmtree(self.tmp_dir)

    def make_action(self, ext_data=None):
        action = Action.create_from(
            opts=self.opts,
            action={
                "id": 1,
                "object_id": self.ext_data["build_id"],
                "object_type": "build",
                "action_type": ActionTypeEnum("finalize_rpm_upload"),
                "data": json.dumps(ext_data or self.ext_data),
            },
            log=self.log,
        )
        action.storage.publish_repository = mock.Mock(return_value=True)
        return action

    @staticmethod
    def fake_download_writing_files():
        # fake side effect for download_file
        def _download(url, destination, log=None):  # pylint: disable=unused-argument
            path = os.path.join(destination, os.path.basename(url))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("fake rpm bytes")
            return path
        return _download

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_success(self, mc_download, mc_nevra, mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mc_nevra.return_value = self.nevra

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("success")
        assert mc_download.call_count == 1
        action.storage.publish_repository.assert_called_once()

        frontend_client = mc_frontend_client.return_value
        frontend_client.update.assert_called_once()
        (payload,), _kwargs = frontend_client.update.call_args
        build_update = payload["builds"][0]
        assert build_update["id"] == 42
        assert build_update["chroot"] == "fedora-40-x86_64"
        assert build_update["status"] == StatusEnum("succeeded")
        assert build_update["results"]["packages"] == [self.nevra]

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_arch_mismatch_is_reported_as_failure(
            self, mc_download, mc_nevra, mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mismatched = dict(self.nevra, arch="aarch64")
        mc_nevra.return_value = mismatched

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("failure")
        action.storage.publish_repository.assert_not_called()

        frontend_client = mc_frontend_client.return_value
        (payload,), _kwargs = frontend_client.update.call_args
        build_update = payload["builds"][0]
        assert build_update["chroot"] == "fedora-40-x86_64"
        assert build_update["status"] == StatusEnum("failed")
        # the reason must be reported back so it's visible to the user
        # (not just in backend logs), see BuildsLogic.update_state_from_dict
        assert "aarch64" in build_update["status_reason"]
        assert "fedora-40-x86_64" in build_update["status_reason"]

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_noarch_is_accepted_for_any_chroot(
            self, mc_download, mc_nevra, _mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mc_nevra.return_value = dict(self.nevra, arch="noarch")

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("success")
        action.storage.publish_repository.assert_called_once()

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_invalid_rpm_is_reported_as_failure(
            self, mc_download, mc_nevra, mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mc_nevra.side_effect = ValueError("not an RPM")

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("failure")
        action.storage.publish_repository.assert_not_called()

        frontend_client = mc_frontend_client.return_value
        (payload,), _kwargs = frontend_client.update.call_args
        assert payload["builds"][0]["status"] == StatusEnum("failed")

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.download_file")
    def test_download_failure_reported_as_failure(
            self, mc_download, mc_frontend_client):
        mc_download.side_effect = OSError("connection refused")

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("failure")
        action.storage.publish_repository.assert_not_called()

        frontend_client = mc_frontend_client.return_value
        (payload,), _kwargs = frontend_client.update.call_args
        assert payload["builds"][0]["status"] == StatusEnum("failed")

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.sign_rpms_in_dir")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_signing_failure_is_reported_as_failure(
            self, mc_download, mc_nevra, mc_sign, _mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mc_nevra.return_value = self.nevra
        mc_sign.side_effect = CoprSignError("signing failed")
        self.opts.do_sign = True

        action = self.make_action()
        result = action.run()

        assert result == BackendResultEnum("failure")
        mc_sign.assert_called_once()
        action.storage.publish_repository.assert_not_called()

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.sign_rpms_in_dir")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_sign_uses_ownername_bare_projectname(
            self, mc_download, mc_nevra, mc_sign, _mc_frontend_client):
        mc_download.side_effect = self.fake_download_writing_files()
        mc_nevra.return_value = self.nevra
        self.opts.do_sign = True

        action = self.make_action()
        action.run()

        args, _kwargs = mc_sign.call_args
        assert args[0] == "foo"  # ownername
        assert args[1] == "bar"  # bare projectname, not project_dirname
        assert args[3] == "fedora-40-x86_64"  # chroot


class TestFinalizeRpmUploadPulpStorage:
    def setup_method(self, _method):
        TestFinalizeRpmUpload.setup_method(self, _method)

    def teardown_method(self, _method):
        TestFinalizeRpmUpload.teardown_method(self, _method)

    def _make_action(self, ext_data=None):
        action = TestFinalizeRpmUpload.make_action(self, ext_data)

        action.storage = mock.Mock()
        action.storage.owner = "foo"
        action.storage.project = "bar"
        action.storage.find_build_results.return_value = [
            "/fake/results/hello-2.8-1.fc40.x86_64.rpm"]
        action.storage.upload_build_results.return_value = {
            "hello-2.8-1.fc40.x86_64.rpm": {"pulp_href": "/pulp/content/abc/"},
        }
        action.storage.create_repository_version.return_value = True
        action.storage.publish_repository.return_value = True
        return action

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_success(self, mc_download, mc_nevra, mc_frontend_client):
        mc_download.side_effect = TestFinalizeRpmUpload.fake_download_writing_files()
        mc_nevra.return_value = self.nevra  # pylint: disable=no-member

        action = self._make_action()
        result = action.run()

        assert result == BackendResultEnum("success")
        action.storage.upload_build_results.assert_called_once()
        rpm_paths, chroot = action.storage.upload_build_results.call_args[0]
        assert chroot == "fedora-40-x86_64"
        assert len(rpm_paths) == 1
        assert action.storage.upload_build_results.call_args.kwargs["build_id"] == 42

        action.storage.create_repository_version.assert_called_once_with(
            "bar", "fedora-40-x86_64", ["/pulp/content/abc/"])

        action.storage.publish_repository.assert_called_once()

        frontend_client = mc_frontend_client.return_value
        (payload,), _kwargs = frontend_client.update.call_args
        assert payload["builds"][0]["status"] == StatusEnum("succeeded")

    @mock.patch("copr_backend.actions.FrontendClient")
    @mock.patch("copr_backend.actions.get_rpm_nevra_dict")
    @mock.patch("copr_backend.actions.download_file")
    def test_repo_version_failure_causes_failure(
            self, mc_download, mc_nevra, mc_frontend_client):
        mc_download.side_effect = TestFinalizeRpmUpload.fake_download_writing_files()
        mc_nevra.return_value = self.nevra  # pylint: disable=no-member

        action = self._make_action()
        action.storage.create_repository_version.return_value = False
        result = action.run()

        assert result == BackendResultEnum("failure")
        action.storage.publish_repository.assert_not_called()

        frontend_client = mc_frontend_client.return_value
        (payload,), _kwargs = frontend_client.update.call_args
        build_update = payload["builds"][0]
        assert build_update["status"] == StatusEnum("failed")
        assert "repository version" in build_update["status_reason"]
