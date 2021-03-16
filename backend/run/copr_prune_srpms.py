#!/usr/bin/python3

"""
Script to prune srpm-builds directories
"""

import os
import sys
import pwd
import shutil
import logging
import argparse
import multiprocessing
from datetime import datetime, timedelta
from copr_backend.helpers import (
    BackendConfigReader,
    get_redis_logger,
    walk_limited,
)


LOG = multiprocessing.log_to_stderr()
LOG.setLevel(logging.INFO)


def get_arg_parser():
    """
    Return argument parser
    """
    parser = argparse.ArgumentParser(
        description="Prune srpm-builds directories")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=("Do not perform any destructive changes, only print what "
              "would happen"))

    parser.add_argument(
        "--stdout",
        action="store_true",
        help=("Print output to the STDOUT instead of logs"))

    parser.add_argument(
        "--days",
        type=int,
        help=("Override `prune_days' from the config file"))

    return parser


def redirect_logging(opts):
    """
    Redirect all logging to RedisLogHandler using BackendConfigReader options
    TODO Taken from `copr_prune_results.py`, move it to some shared place
    """
    global LOG  # pylint: disable=global-statement
    LOG = get_redis_logger(opts, "copr_prune_results", "pruner")


def prune(path, days, dry_run=False, stdout=False):
    """
    Recursively go through the results directory and remove all stored SRPM
    packages, that are too old.
    """
    path = os.path.normpath(path)
    for root, subdirs, _ in walk_limited(path, mindepth=3, maxdepth=3):
        parsed = os.path.normpath(root).split(os.sep)

        if parsed[-1] != "srpm-builds":
            continue

        for subdir in subdirs:
            subdir = os.path.join(root, subdir)
            modified = datetime.fromtimestamp(os.path.getmtime(subdir))
            too_old = datetime.now() - timedelta(days=days)

            if modified >= too_old:
                continue

            date = modified.strftime("%Y-%m-%d")
            if stdout:
                print("Removing: {0}  ({1})".format(subdir, date))
            else:
                LOG.info("Removing: %s  (%s)", subdir, date)

            if not dry_run:
                shutil.rmtree(subdir)


def main():
    """
    Main function
    """
    parser = get_arg_parser()
    args = parser.parse_args()
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    opts = BackendConfigReader(config_file).read()
    days = args.days if args.days is not None else opts.prune_days
    redirect_logging(opts)
    prune(opts.destdir, days, args.dry_run, args.stdout)


if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    main()
