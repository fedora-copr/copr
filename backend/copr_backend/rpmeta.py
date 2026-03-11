"""
Wrapper between copr-backend and rpmeta API.
"""

import json
import logging
import os

import requests

from copr_backend.helpers import create_file_logger


def _get_predictions_logger(log_dir):
    """
    Return a logger that writes JSON lines to
    ``<log_dir>/rpmeta-predictions.log``.
    """
    path = os.path.join(log_dir, "rpmeta-predictions.log")
    fmt = logging.Formatter("%(message)s")
    logger = create_file_logger("rpmeta-predictions", path, fmt=fmt)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def parse_version(package_version):
    """
    Split an EVR string like "2:1.5.0-3.fc44" into (epoch, version),
    stripping the release part.

    Returns:
     - (0, "0") for None/empty input.
     - (epoch, version) for valid input.
    """
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


def rpmeta_predict_build_time(job, opts, log):
    """
    Query rpmeta for a build time prediction (in minutes).

    Returns the predicted build time as a number, or None when the
    prediction is unavailable (disabled, unsupported arch, API error, …).

    This function never raises -- all errors are caught and logged so that
    the build proceeds normally regardless of rpmeta availability.
    """
    try:
        return _rpmeta_predict_inner(job, opts, log)
    except Exception:  # pylint: disable=broad-exception-caught
        log.warning("rpmeta: unexpected error", exc_info=True)
        return None


def _rpmeta_predict_inner(job, opts, log):  # pylint: disable=too-many-return-statements
    if not getattr(opts, "rpmeta_enabled", False):
        return None

    if not opts.rpmeta_url:
        log.warning("rpmeta: enabled but rpmeta_url is not configured, skipping")
        return None

    if job.chroot == "srpm-builds":
        return None

    hw_info_map = getattr(opts, "rpmeta_hw_info", {})
    if not hw_info_map:
        return None

    hw_info = hw_info_map.get(job.arch)
    if hw_info is None:
        log.info("rpmeta: no HW info for arch %s, skipping", job.arch)
        return None

    if hw_info.get("cpu_arch") != job.arch:
        log.info("rpmeta: skipping %s build, hw_info cpu_arch is emulated (%s)",
                 job.arch, hw_info.get("cpu_arch"))
        return None

    epoch, version = parse_version(job.package_version)
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
        return None
    except requests.exceptions.ConnectionError:
        log.warning("rpmeta: cannot connect to %s, skipping", opts.rpmeta_url)
        return None

    if resp.status_code == 404:
        log.info("rpmeta: package %s not known to model, skipping",
                 job.package_name)
        return None

    if resp.status_code != 200:
        log.warning("rpmeta: API returned %s: %s",
                     resp.status_code, resp.text[:800])
        return None

    try:
        prediction = resp.json().get("prediction")
    except (ValueError, AttributeError):
        log.warning("rpmeta: API returned 200 but response is not valid JSON")
        return None

    if prediction is None:
        log.warning("rpmeta: API returned 200 but no prediction value")
        return None

    # 120 is a magic number here, logic of deciding which VM specs to use will change in the
    # future. For now, anything above 120 minutes is considered in need of a powerful builder.
    recommends_powerful = prediction >= 120

    prediction_logger = _get_predictions_logger(opts.log_dir)
    prediction_logger.info(json.dumps({
        "build_id": job.build_id,
        "prediction": prediction,
        "recommends_powerful": recommends_powerful,
        "has_powerful_tag": "on_demand_powerful" in job.tags,
    }))

    if recommends_powerful:
        log.info("rpmeta: predicted %d min for %s on %s "
                 "-> recommends powerful builder (no build promotion)",
                 prediction, job.package_name, job.chroot)
    else:
        log.info("rpmeta: predicted %d min for %s on %s "
                 "-> normal builder sufficient",
                 prediction, job.package_name, job.chroot)

    return prediction
