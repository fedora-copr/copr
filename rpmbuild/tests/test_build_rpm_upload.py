import hashlib
import json
import os
import tarfile
import tempfile

import pytest

from main import build_rpm, build_rpm_upload
from copr_rpmbuild.rpm_upload import process_uploaded_tarball

from . import TestCase

try:
    from unittest import mock
except ImportError:
    import mock


RPM_NAME = "hello-2.8-1.fc40.x86_64.rpm"
RPM_CONTENT = b"fake rpm content"
CHROOT = "fedora-40-x86_64"


def _fake_header(arch):
    return {
        "name": "hello",
        "epoch": None,
        "version": "2.8",
        "release": "1",
        "arch": arch,
    }


def _sha256_of_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _build_upload_tarball(files, dirname="upload"):
    tarball_fd, tarball_path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(tarball_fd)
    try:
        with tempfile.TemporaryDirectory() as workdir:
            content_dir = os.path.join(workdir, dirname)
            os.makedirs(content_dir)
            for filename, content in files.items():
                with open(os.path.join(content_dir, filename), "wb") as handle:
                    handle.write(content)
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(content_dir, arcname=dirname)
    except Exception:
        os.unlink(tarball_path)
        raise
    return tarball_path


class TestRpmUploadTarball(TestCase):

    config = {}
    workdir = None
    resultdir = None
    workspace = None

    def auto_test_setup(self):
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    def _process_tarball(self, files, chroot=CHROOT, header_arch="x86_64"):
        tarball_path = _build_upload_tarball(files)
        try:
            with mock.patch(
                    "copr_rpmbuild.rpm_upload.get_rpm_header") as mc_get_header:
                mc_get_header.return_value = _fake_header(header_arch)
                process_uploaded_tarball(tarball_path, self.resultdir, chroot)
                return mc_get_header
        finally:
            os.unlink(tarball_path)

    def test_process_publishes_rpm_and_files(self):
        self._process_tarball({
            RPM_NAME: RPM_CONTENT,
            "sha256.json": json.dumps({
                RPM_NAME: _sha256_of_bytes(RPM_CONTENT),
            }).encode("utf-8"),
            "hello-2.8-1.fc40.src.rpm": b"fake srpm content",
            "build.log": b"build log",
            "README.txt": b"notes",
        })

        assert os.path.exists(os.path.join(self.resultdir, RPM_NAME))
        assert os.path.exists(os.path.join(
            self.resultdir, "hello-2.8-1.fc40.src.rpm"))

        logs_tarball = os.path.join(self.resultdir, "uploaded-logs.tar.gz")
        assert os.path.exists(logs_tarball)
        with tarfile.open(logs_tarball, "r:gz") as tar:
            assert sorted(tar.getnames()) == ["README.txt", "build.log"]

    def test_process_noarch_is_allowed(self):
        self._process_tarball(
            {"hello-2.8-1.fc40.noarch.rpm": RPM_CONTENT},
            header_arch="noarch",
        )
        assert os.path.exists(os.path.join(
            self.resultdir, "hello-2.8-1.fc40.noarch.rpm"))

    def test_process_sha256_failures(self):
        with pytest.raises(RuntimeError) as error:
            self._process_tarball({
                RPM_NAME: RPM_CONTENT,
                "sha256.json": json.dumps({
                    RPM_NAME: "0" * 64,
                    "missing.rpm": "1" * 64,
                }).encode("utf-8"),
            })
        message = str(error.value)
        assert "SHA256 mismatch" in message
        assert "not found: missing.rpm" in message

    def test_process_rejects_arch_mismatch(self):
        with pytest.raises(RuntimeError) as error:
            self._process_tarball(
                {RPM_NAME: RPM_CONTENT}, header_arch="aarch64")
        assert "aarch64" in str(error.value)

    def test_process_allows_i686_on_i386_chroot(self):
        self._process_tarball(
            {RPM_NAME: RPM_CONTENT},
            chroot="fedora-40-i386",
            header_arch="i686",
        )
        assert os.path.exists(os.path.join(self.resultdir, RPM_NAME))

    def test_process_rejects_no_binary_rpms(self):
        with pytest.raises(RuntimeError) as error:
            self._process_tarball(
                {"hello-2.8-1.fc40.src.rpm": b"fake srpm content"})
        assert "at least one binary RPM" in str(error.value)

    def test_process_rejects_multiple_srpms(self):
        with pytest.raises(RuntimeError) as error:
            self._process_tarball({
                RPM_NAME: RPM_CONTENT,
                "hello-2.8-1.fc40.src.rpm": b"fake srpm content",
                "hello-2.8-1.fc40.nosrc.rpm": b"fake nosrc content",
            })
        assert "at most one SRPM" in str(error.value)


class TestBuildRpmUpload(TestCase):

    config = {}
    workdir = None
    resultdir = None
    workspace = None

    task = {
        "chroot": CHROOT,
        "package_name": None,
        "prebuilt_tarball_url": (
            "https://copr.example.com/tmp/abc/upload.tar.gz"),
    }

    def auto_test_setup(self):
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    @mock.patch("main.run_automation_tools")
    @mock.patch("main.process_uploaded_tarball")
    @mock.patch("main.download_file")
    def test_build_rpm_upload_success(
            self, mc_download, mc_process, mc_run_automation_tools):
        tarball_fd, tarball_path = tempfile.mkstemp(suffix=".tar.gz")
        os.close(tarball_fd)
        mc_download.return_value = tarball_path

        build_rpm_upload(self.task, self.config)

        mc_download.assert_called_once_with(
            self.task["prebuilt_tarball_url"], self.resultdir)
        mc_process.assert_called_once_with(
            tarball_path, self.resultdir, self.task["chroot"])
        assert not os.path.exists(tarball_path)

        success_file = os.path.join(self.resultdir, "success")
        assert os.path.exists(success_file)
        with open(success_file, encoding="utf-8") as fd:
            assert fd.read() == "done"

        mc_run_automation_tools.assert_called_once_with(
            self.task, self.resultdir, None, mock.ANY, self.config)

    def test_build_rpm_upload_download_failure(self):
        with mock.patch("main.run_automation_tools") as mc_run_automation_tools:
            with mock.patch("main.download_file") as mc_download:
                mc_download.side_effect = RuntimeError("Failed to download")

                with pytest.raises(RuntimeError):
                    build_rpm_upload(self.task, self.config)

                mc_run_automation_tools.assert_not_called()


class TestBuildRpmDispatch(TestCase):

    config = {}
    workdir = None
    resultdir = None
    workspace = None

    def auto_test_setup(self):
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    @mock.patch("main.build_rpm_upload")
    @mock.patch("main.providers.DistGitProvider")
    @mock.patch("main.log_task")
    @mock.patch("main.get_task")
    def test_build_rpm_routes_prebuilt_tarball_url(
            self, mc_get_task, _mc_log_task, mc_distgit, mc_build_rpm_upload):
        task = {
            "chroot": CHROOT,
            "prebuilt_tarball_url": (
                "https://copr.example.com/tmp/abc/upload.tar.gz"),
        }
        mc_get_task.return_value = task
        args = mock.Mock(chroot=CHROOT, build_id="123", copr=None)

        build_rpm(args, self.config)

        mc_build_rpm_upload.assert_called_once_with(task, self.config)
        mc_distgit.assert_not_called()
