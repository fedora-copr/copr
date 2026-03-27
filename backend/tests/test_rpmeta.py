"""Tests for copr_backend.rpmeta wrapper module."""

import json
import os
import tempfile
import shutil
import requests
from unittest import mock

import pytest

from copr_backend import rpmeta


SAMPLE_HW_CONFIG = """\
x86_64:
  cpu_model_name: "AMD EPYC 7R13"
  cpu_arch: "x86_64"
  cpu_model: "1"
  cpu_cores: 4
  ram: 16.0
  swap: 0.0

aarch64:
  cpu_model_name: "Neoverse-N1"
  cpu_arch: "aarch64"
  cpu_model: "1"
  cpu_cores: 4
  ram: 16.0
  swap: 0.0
"""


def _make_job(**kwargs):
    defaults = {
        "chroot": "fedora-41-x86_64",
        "arch": "x86_64",
        "tags": ["copr_builder", "arch_x86_64"],
        "package_name": "test-pkg",
        "package_version": "0:1.2.3-1.fc41",
        "build_id": 12345,
    }
    defaults.update(kwargs)
    return mock.MagicMock(**defaults)


def _make_opts(tmpdir, config_path=None, **overrides):
    defaults = {
        "rpmeta_enabled": True,
        "rpmeta_url": "http://localhost:44882",
        "rpmeta_timeout": 5,
        "rpmeta_hw_pools_config": config_path,
        "log_dir": tmpdir,
    }
    defaults.update(overrides)
    return mock.MagicMock(**defaults)


@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset module-level caches between tests."""
    rpmeta._hw_info_cache = None
    rpmeta._predictions_logger = None
    yield
    rpmeta._hw_info_cache = None
    rpmeta._predictions_logger = None


@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp(prefix="copr-test-rpmeta-")
    yield d
    shutil.rmtree(d)


@pytest.fixture
def config_file(tmpdir):
    path = os.path.join(tmpdir, "hw-info.yaml")
    with open(path, "w") as fh:
        fh.write(SAMPLE_HW_CONFIG)
    return path


class TestLoadHwInfo:
    def test_caches_result(self, config_file):
        log = mock.MagicMock()
        data1 = rpmeta._load_hw_info(config_file, log)
        data2 = rpmeta._load_hw_info(config_file, log)
        assert data1 is data2


class TestParseVersion:
    def test_full_evr(self):
        assert rpmeta._parse_version("2:1.5.0-3.fc44") == (2, "1.5.0")

    def test_no_epoch(self):
        assert rpmeta._parse_version("3.2.1-1.fc44") == (0, "3.2.1")

    def test_none(self):
        assert rpmeta._parse_version(None) == (0, "0")

    def test_version_only(self):
        assert rpmeta._parse_version("1.0") == (0, "1.0")


class TestLogRpmetaPrediction:
    def test_disabled(self, tmpdir, config_file):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir, config_file, rpmeta_enabled=False)
        rpmeta.log_rpmeta_prediction(_make_job(), opts, log)
        log.info.assert_not_called()

    def test_srpm_build_skipped(self, tmpdir, config_file):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir, config_file)
        rpmeta.log_rpmeta_prediction(
            _make_job(chroot="srpm-builds"), opts, log)
        log.info.assert_not_called()

    def test_unknown_arch_skipped(self, tmpdir, config_file):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir, config_file)
        rpmeta.log_rpmeta_prediction(
            _make_job(chroot="fedora-42-riscv64", arch="riscv64"), opts, log)
        log.info.assert_called()
        assert "no HW info for arch" in log.info.call_args[0][0]

    @pytest.mark.parametrize("prediction_val,tags,expect_powerful,expect_powerful_tag,expect_log_substr", [
        (30, ["copr_builder", "arch_x86_64"], False, False, "normal builder sufficient"),
        (185, ["copr_builder", "arch_x86_64"], True, False, "recommends powerful"),
        (10, ["copr_builder", "arch_x86_64", "on_demand_powerful"], False, True, "normal builder sufficient"),
    ])
    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_successful_prediction(self, mock_post, tmpdir, config_file,
                                   prediction_val, tags, expect_powerful,
                                   expect_powerful_tag, expect_log_substr):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"prediction": prediction_val}
        mock_post.return_value = mock_resp

        log = mock.MagicMock()
        opts = _make_opts(tmpdir, config_file)
        job = _make_job(tags=tags)

        rpmeta.log_rpmeta_prediction(job, opts, log)

        payload = mock_post.call_args[1]["json"]
        assert payload["package_name"] == "test-pkg"
        assert payload["hw_info"]["cpu_arch"] == "x86_64"
        assert expect_log_substr in log.info.call_args[0][0]

        pred_log = os.path.join(tmpdir, "rpmeta-predictions.log")
        with open(pred_log) as fh:
            record = json.loads(fh.readline())

        assert record["build_id"] == 12345
        assert record["prediction"] == prediction_val
        assert record["recommends_powerful"] is expect_powerful
        assert record["has_powerful_tag"] is expect_powerful_tag

    @pytest.mark.parametrize("side_effect,status_code,expect_log_method,expect_log_substr", [
        (None, 404, "info", "not known to model"),
        ("timeout", None, "warning", "timed out"),
        ("connection", None, "warning", "cannot connect"),
        ("runtime", None, "warning", "unexpected error"),
    ])
    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_error_handling(self, mock_post, tmpdir, config_file,
                            side_effect, status_code, expect_log_method,
                            expect_log_substr):
        if side_effect == "timeout":
            mock_post.side_effect = requests.exceptions.Timeout("timed out")
        elif side_effect == "connection":
            mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        elif side_effect == "runtime":
            mock_post.side_effect = RuntimeError("boom! disaster!!!!")
        else:
            mock_resp = mock.MagicMock()
            mock_resp.status_code = status_code
            mock_post.return_value = mock_resp

        log = mock.MagicMock()
        opts = _make_opts(tmpdir, config_file)

        rpmeta.log_rpmeta_prediction(_make_job(), opts, log)
        log_method = getattr(log, expect_log_method)
        log_method.assert_called()
        assert expect_log_substr in log_method.call_args[0][0]
