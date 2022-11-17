"""
Common Copr code for logging
"""

import logging


def setup_script_logger(log, path):
    """
    Backend scripts should simply do:

        log = logging.getLogger(__name__)
        setup_script_logger(log, "/var/log/copr-backend/foo.log")
    """

    # Don't read copr config, just use INFO. Scripts should implement
    # some --verbose parameter for debug information
    log.setLevel(logging.INFO)

    # Drop the default handler, we will create it ourselves
    log.handlers = []

    # Print also to stderr
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(stream)

    # Add file logging
    file_log = logging.FileHandler(path)
    file_log_format = "[%(asctime)s][%(levelname)6s]: %(message)s"
    file_log.setFormatter(logging.Formatter(file_log_format))
    log.addHandler(file_log)

    return log
