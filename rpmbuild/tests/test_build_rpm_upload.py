import os

import pytest

from main import build_rpm, build_rpm_upload

from . import TestCase

try:
    from unittest import mock
except ImportError:
    # Python 2 version depends on mock
    import mock


def _fake_header(arch):
    return {
        "name": "hello",
        "epoch": None,
        "version": "2.8",
        "release": "1",
        "arch": arch,
    }


class TestBuildRpmUpload(TestCase):

    config = {}
    workdir = None
    resultdir = None
    workspace = None

    task = {
        "chroot": "fedora-40-x86_64",
        "package_name": None,
        "prebuilt_rpm_urls": [
            "https://copr.example.com/tmp/abc/hello-2.8-1.fc40.x86_64.rpm",
        ],
    }

    def auto_test_setup(self):
        self.config_basic_dirs()

    def auto_test_cleanup(self):
        self.cleanup_basic_dirs()

    @staticmethod
    def _fake_download_file(url, destination):
        filename = os.path.basename(url)
        path = os.path.join(destination, filename)
        with open(path, "w", encoding="utf-8") as fd:
            fd.write("fake rpm content")
        return path

    @mock.patch("main.run_automation_tools")
    @mock.patch("main.get_rpm_header")
    @mock.patch("main.download_file")
    def test_build_rpm_upload_success(self, mc_download, mc_get_header,
                                      mc_run_automation_tools):
        mc_download.side_effect = self._fake_download_file
        mc_get_header.return_value = _fake_header("x86_64")

        build_rpm_upload(self.task, self.config)

        mc_download.assert_called_once_with(
            self.task["prebuilt_rpm_urls"][0], self.resultdir)

        success_file = os.path.join(self.resultdir, "success")
        assert os.path.exists(success_file)
        with open(success_file, encoding="utf-8") as fd:
            assert fd.read() == "done"

        mc_run_automation_tools.assert_called_once_with(
            self.task, self.resultdir, None, mock.ANY, self.config)

    @mock.patch("main.run_automation_tools")
    @mock.patch("main.get_rpm_header")
    @mock.patch("main.download_file")
    def test_build_rpm_upload_noarch_is_allowed(self, mc_download,
                                                mc_get_header,
                                                mc_run_automation_tools):
        mc_download.side_effect = self._fake_download_file
        mc_get_header.return_value = _fake_header("noarch")

        build_rpm_upload(self.task, self.config)

        assert os.path.exists(os.path.join(self.resultdir, "success"))
        mc_run_automation_tools.assert_called_once()

    @mock.patch("main.run_automation_tools")
    @mock.patch("main.get_rpm_header")
    @mock.patch("main.download_file")
    def test_build_rpm_upload_arch_mismatch(self, mc_download, mc_get_header,
                                            mc_run_automation_tools):
        mc_download.side_effect = self._fake_download_file
        mc_get_header.return_value = _fake_header("aarch64")

        with pytest.raises(RuntimeError) as error:
            build_rpm_upload(self.task, self.config)

        assert "aarch64" in str(error.value)
        assert "fedora-40-x86_64" in str(error.value)

        # a failed validation must not leave a stray success marker, and
        # results.json must not be generated for a failed task
        assert not os.path.exists(os.path.join(self.resultdir, "success"))
        mc_run_automation_tools.assert_not_called()

    @mock.patch("main.run_automation_tools")
    @mock.patch("main.get_rpm_header")
    @mock.patch("main.download_file")
    def test_build_rpm_upload_download_failure(self, mc_download,
                                               mc_get_header,
                                               mc_run_automation_tools):
        mc_download.side_effect = RuntimeError("Failed to download")

        with pytest.raises(RuntimeError):
            build_rpm_upload(self.task, self.config)

        mc_get_header.assert_not_called()
        mc_run_automation_tools.assert_not_called()


class TestBuildRpmDispatch(TestCase):
    """
    Make sure build_rpm() routes "direct RPM upload" tasks to
    build_rpm_upload() instead of the normal DistGit+Mock flow.
    """

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
    def test_build_rpm_routes_prebuilt_rpm_urls(
            self, mc_get_task, _mc_log_task, mc_distgit, mc_build_rpm_upload):
        task = {
            "chroot": "fedora-40-x86_64",
            "prebuilt_rpm_urls": ["https://copr.example.com/tmp/abc/hello.rpm"],
        }
        mc_get_task.return_value = task
        args = mock.Mock(chroot="fedora-40-x86_64", build_id="123", copr=None)

        build_rpm(args, self.config)

        mc_build_rpm_upload.assert_called_once_with(task, self.config)
        mc_distgit.assert_not_called()
