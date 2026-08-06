"""Tests for copr_backend.rpmeta wrapper module."""
# pylint: disable=redefined-outer-name

import json
import logging
import os
import tempfile
import shutil
from unittest import mock

import pytest
import requests
from munch import Munch

from copr_backend import rpmeta
from copr_backend.rpmeta import _load_rpmeta_hw_info


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


def _make_opts(tmpdir, **overrides):
    hw_path = os.path.join(tmpdir, "hw-info.yaml")
    if not os.path.exists(hw_path):
        with open(hw_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_HW_CONFIG)
    defaults = {
        "rpmeta_enabled": True,
        "rpmeta_url": "http://localhost:44882",
        "rpmeta_timeout": 5,
        "rpmeta_hw_pools_config": hw_path,
        "rpmeta_powerful_threshold": 120,
        "log_dir": tmpdir,
    }
    defaults.update(overrides)
    return Munch(defaults)


def _mock_prediction(prediction_val):
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"prediction": prediction_val}
    return mock_resp


@pytest.fixture(autouse=True)
def _reset_predictions_logger():
    """Clear the cached predictions logger so each test gets a fresh handler."""
    yield
    logger = logging.getLogger("rpmeta-predictions")
    logger.handlers.clear()


@pytest.fixture
def tmpdir():
    d = tempfile.mkdtemp(prefix="copr-test-rpmeta-")
    yield d
    shutil.rmtree(d)


@pytest.fixture
def config_file(tmpdir):
    path = os.path.join(tmpdir, "hw-info.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_HW_CONFIG)
    return path


class TestLoadRpmetaHwInfo:
    def test_loads_valid_config(self, config_file):
        log = mock.MagicMock()
        data = _load_rpmeta_hw_info(config_file, log)
        assert "x86_64" in data
        assert data["x86_64"]["cpu_arch"] == "x86_64"
        assert data["aarch64"]["cpu_cores"] == 4
        log.warning.assert_not_called()

    def test_missing_file_returns_empty(self, tmpdir):
        log = mock.MagicMock()
        data = _load_rpmeta_hw_info(os.path.join(tmpdir, "nonexistent.yaml"), log)
        assert data == {}
        log.warning.assert_called()

    def test_none_path_returns_empty(self):
        log = mock.MagicMock()
        data = _load_rpmeta_hw_info(None, log)
        assert data == {}
        log.warning.assert_called()

    def test_invalid_yaml_returns_empty(self, tmpdir):
        log = mock.MagicMock()
        path = os.path.join(tmpdir, "bad.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{{{{not valid yaml: [")
        data = _load_rpmeta_hw_info(path, log)
        assert data == {}
        log.warning.assert_called()


class TestParseVersion:
    def test_full_evr(self):
        assert rpmeta.parse_version("2:1.5.0-3.fc44") == (2, "1.5.0")

    def test_no_epoch(self):
        assert rpmeta.parse_version("3.2.1-1.fc44") == (0, "3.2.1")

    def test_none(self):
        assert rpmeta.parse_version(None) == (0, "0")

    def test_version_only(self):
        assert rpmeta.parse_version("1.0") == (0, "1.0")


class TestRpmetaPredictBuildTime:
    def test_disabled(self, tmpdir):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir, rpmeta_enabled=False)
        assert rpmeta.rpmeta_predict_build_time(_make_job(), opts, log) is None
        log.info.assert_not_called()

    def test_missing_url(self, tmpdir):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir, rpmeta_url=None)
        assert rpmeta.rpmeta_predict_build_time(_make_job(), opts, log) is None
        log.warning.assert_called()
        assert "rpmeta_url is not configured" in log.warning.call_args[0][0]

    def test_srpm_build_skipped(self, tmpdir):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        assert rpmeta.rpmeta_predict_build_time(
            _make_job(chroot="srpm-builds"), opts, log) is None
        log.info.assert_not_called()

    def test_unknown_arch_skipped(self, tmpdir):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        assert rpmeta.rpmeta_predict_build_time(
            _make_job(chroot="fedora-42-riscv64", arch="riscv64"), opts, log) is None
        log.info.assert_called()
        assert "no HW info for arch" in log.info.call_args[0][0]

    @pytest.mark.parametrize(
        "prediction_val,tags,expect_final_tag,expect_promoted,expect_log_substr", [
            # Never tagged, below threshold -> stays untouched.
            (30, ["copr_builder", "arch_x86_64"],
             False, False, "normal builder sufficient"),
            # Never tagged, above threshold -> promoted (tag added).
            (185, ["copr_builder", "arch_x86_64"],
             True, True, "promoted to powerful builder"),
            # Already tagged, below threshold -> rpmeta never demotes.
            (30, ["copr_builder", "arch_x86_64", "on_demand_powerful"],
             True, False, "keeping powerful builder tag"),
            # Already tagged, above threshold -> tag is kept.
            (185, ["copr_builder", "arch_x86_64", "on_demand_powerful"],
             True, False, "keeping powerful builder tag"),
        ])
    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_successful_prediction(self, mock_post, tmpdir,
                                   prediction_val, tags, expect_final_tag,
                                   expect_promoted, expect_log_substr):
        mock_post.return_value = _mock_prediction(prediction_val)

        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        job = _make_job(tags=list(tags))

        result = rpmeta.rpmeta_predict_build_time(job, opts, log)
        assert result == prediction_val

        payload = mock_post.call_args[1]["json"]
        assert payload["package_name"] == "test-pkg"
        assert payload["hw_info"]["cpu_arch"] == "x86_64"
        assert expect_log_substr in log.info.call_args[0][0]

        assert ("on_demand_powerful" in job.tags) is expect_final_tag

        pred_log = os.path.join(tmpdir, "rpmeta-predictions.log")
        with open(pred_log, encoding="utf-8") as fh:
            record = json.loads(fh.readline())

        assert record["build_id"] == 12345
        assert record["chroot"] == "fedora-41-x86_64"
        assert record["arch"] == "x86_64"
        assert record["package_name"] == "test-pkg"
        assert record["package_version"] == "0:1.2.3-1.fc41"
        assert record["prediction"] == prediction_val
        assert record["threshold"] == 120
        assert record["recommends_powerful"] is (prediction_val >= 120)
        assert record["has_powerful_tag"] is expect_final_tag
        assert record["promoted"] is expect_promoted

    def test_promotes_untagged_job_above_threshold(self, tmpdir):
        """rpmeta adds the powerful tag to any build predicted above threshold."""
        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        job = _make_job(tags=["copr_builder", "arch_x86_64"])

        with mock.patch("copr_backend.rpmeta.requests.post") as mock_post:
            mock_post.return_value = _mock_prediction(500)
            rpmeta.rpmeta_predict_build_time(job, opts, log)

        assert job.tags == ["copr_builder", "arch_x86_64", "on_demand_powerful"]

    def test_never_removes_existing_tag(self, tmpdir):
        """rpmeta must never demote a build that already has the powerful tag."""
        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        job = _make_job(tags=["copr_builder", "arch_x86_64", "on_demand_powerful"])

        with mock.patch("copr_backend.rpmeta.requests.post") as mock_post:
            mock_post.return_value = _mock_prediction(10)
            rpmeta.rpmeta_predict_build_time(job, opts, log)

        assert job.tags == ["copr_builder", "arch_x86_64", "on_demand_powerful"]

    def test_keeps_tag_when_still_above_threshold(self, tmpdir):
        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        job = _make_job(tags=["copr_builder", "arch_x86_64", "on_demand_powerful"])

        with mock.patch("copr_backend.rpmeta.requests.post") as mock_post:
            mock_post.return_value = _mock_prediction(200)
            rpmeta.rpmeta_predict_build_time(job, opts, log)

        assert job.tags == ["copr_builder", "arch_x86_64", "on_demand_powerful"]

    @pytest.mark.parametrize("threshold,prediction_val,expect_promoted", [
        (120, 119, False),
        (120, 120, True),
        (30, 29, False),
        (300, 299, False),
        (300, 300, True),
    ])
    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_configurable_threshold(self, mock_post, tmpdir,
                                    threshold, prediction_val, expect_promoted):
        mock_post.return_value = _mock_prediction(prediction_val)

        log = mock.MagicMock()
        opts = _make_opts(tmpdir, rpmeta_powerful_threshold=threshold)
        job = _make_job(tags=["copr_builder", "arch_x86_64"])
        result = rpmeta.rpmeta_predict_build_time(job, opts, log)
        assert result == prediction_val
        assert ("on_demand_powerful" in job.tags) is expect_promoted

        pred_log = os.path.join(tmpdir, "rpmeta-predictions.log")
        with open(pred_log, encoding="utf-8") as fh:
            record = json.loads(fh.readline())
        assert record["promoted"] is expect_promoted

    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_default_threshold_when_not_configured(self, mock_post, tmpdir):
        mock_post.return_value = _mock_prediction(150)

        log = mock.MagicMock()
        opts = _make_opts(tmpdir)
        del opts["rpmeta_powerful_threshold"]

        job = _make_job(tags=["copr_builder", "arch_x86_64"])
        result = rpmeta.rpmeta_predict_build_time(job, opts, log)
        assert result == 150
        # 150 >= the default threshold of 120 -> promoted.
        assert "on_demand_powerful" in job.tags

    @pytest.mark.parametrize("side_effect,status_code,expect_log_method,expect_log_substr", [
        (None, 404, "info", "not known to model"),
        ("timeout", None, "warning", "timed out"),
        ("connection", None, "warning", "cannot connect"),
        ("runtime", None, "warning", "unexpected error"),
    ])
    @mock.patch("copr_backend.rpmeta.requests.post")
    def test_error_handling(self, mock_post, tmpdir,
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
        opts = _make_opts(tmpdir)

        assert rpmeta.rpmeta_predict_build_time(_make_job(), opts, log) is None
        log_method = getattr(log, expect_log_method)
        log_method.assert_called()
        assert expect_log_substr in log_method.call_args[0][0]
