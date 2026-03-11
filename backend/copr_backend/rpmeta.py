"""
Wrapper between copr-backend and rpmeta API.
"""

import json
import logging
import logging.handlers
import os

import requests
import yaml


_hw_info_cache = None
_predictions_logger = None


def _get_predictions_logger(log_dir):
    """
    Return (or lazily create) a logger that writes JSON lines to
    ``<log_dir>/rpmeta-predictions.log``.
    """
    global _predictions_logger
    if _predictions_logger is not None:
        return _predictions_logger

    logger = logging.getLogger("rpmeta-predictions")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        path = os.path.join(log_dir, "rpmeta-predictions.log")
        handler = logging.handlers.WatchedFileHandler(path)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _predictions_logger = logger
    return logger


def _load_hw_info(config_path, log):
    global _hw_info_cache
    if _hw_info_cache is not None:
        return _hw_info_cache

    if not config_path or not os.path.exists(config_path):
        log.warning("rpmeta: HW info config not found at %s, "
                     "predictions disabled", config_path)
        _hw_info_cache = {}
        return _hw_info_cache

    try:
        with open(config_path, "r") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        log.warning("rpmeta: failed to parse HW info config %s: %s",
                     config_path, exc)
        _hw_info_cache = {}
        return _hw_info_cache

    _hw_info_cache = data
    return _hw_info_cache


def _parse_version(package_version):
    if not package_version:
        return 0, "0"

    pv = package_version
    epoch = 0
    if ":" in pv:
        epoch_str, pv = pv.split(":", 1)
        try:
            epoch = int(epoch_str)
        except ValueError:
            pass

    version = pv.rsplit("-", 1)[0] if "-" in pv else pv
    return epoch, version


def log_rpmeta_prediction(job, opts, log):
    """
    Query rpmeta for a build time prediction and log the result to both the
    dedicated predictions log and the per-build backend.log.

    This function never raises -- all errors are caught and logged so that
    the build proceeds normally regardless of rpmeta availability.
    """
    try:
        _log_rpmeta_prediction_inner(job, opts, log)
    except Exception:
        log.warning("rpmeta: unexpected error", exc_info=True)


def _log_rpmeta_prediction_inner(job, opts, log):
    if not getattr(opts, "rpmeta_enabled", False):
        return

    if job.chroot == "srpm-builds":
        return

    hw_info_map = _load_hw_info(
        getattr(opts, "rpmeta_hw_pools_config", None), log)
    if not hw_info_map:
        return

    hw_info = hw_info_map.get(job.arch)
    if hw_info is None:
        log.info("rpmeta: no HW info for arch %s, skipping", job.arch)
        return

    if hw_info.get("cpu_arch") != job.arch:
        log.info("rpmeta: skipping %s build, hw_info cpu_arch is emulated (%s)",
                 job.arch, hw_info.get("cpu_arch"))
        return

    epoch, version = _parse_version(job.package_version)
    payload = {
        "package_name": job.package_name,
        "epoch": epoch,
        "version": version,
        "mock_chroot": job.chroot,
        "hw_info": hw_info,
        "configuration": {"time_format": "minutes"},
    }

    try:
        resp = requests.post(
            f"{opts.rpmeta_url}/predict",
            json=payload,
            timeout=opts.rpmeta_timeout,
        )
    except requests.exceptions.Timeout:
        log.warning("rpmeta: API call timed out after %ss, skipping", opts.rpmeta_timeout)
        return
    except requests.exceptions.ConnectionError:
        log.warning("rpmeta: cannot connect to %s, skipping", opts.rpmeta_url)
        return

    if resp.status_code == 404:
        log.info("rpmeta: package %s not known to model, skipping",
                 job.package_name)
        return

    if resp.status_code != 200:
        log.warning("rpmeta: API returned %s: %s",
                     resp.status_code, resp.text[:200])
        return

    prediction = resp.json().get("prediction")
    # 120 is a magic number here, logic of deciding which VM specs to use will change in the
    # future. For now, anything above 120 minutes is considered in need of a powerful builder.
    recommends_powerful = prediction >= 120

    # logger file for first round of monitoring, will delete later
    prediction_logger = _get_predictions_logger(opts.log_dir)
    prediction_logger.info(
        json.dumps(
            {
                "build_id": job.build_id,
                "prediction": prediction,
                "recommends_powerful": recommends_powerful,
                "has_powerful_tag": "on_demand_powerful" in job.tags,
            },
            indent=4,
        )
    )

    if recommends_powerful:
        log.info("rpmeta: predicted %d min for %s on %s "
                 "-> recommends powerful builder (no build promotion)",
                 prediction, job.package_name, job.chroot)
    else:
        log.info("rpmeta: predicted %d min for %s on %s "
                 "-> normal builder sufficient",
                 prediction, job.package_name, job.chroot)
