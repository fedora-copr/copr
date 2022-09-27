"""
Common Copr code for logging
"""

import sys
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

    # Print to stdout
    stdout_log = logging.StreamHandler(sys.stdout)
    stdout_log.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(stdout_log)

    # Add file logging
    file_log = logging.FileHandler(path)
    log.addHandler(file_log)

    return log
