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
from copr_common.tree import walk_limited
from copr_backend.helpers import (
    BackendConfigReader,
    get_redis_logger,
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


def print_remove_text(path, modified, stdout=False):
    """
    Just a little helper function so we don't have to repeat the `if stdout`
    condition everywhere
    """
    date = modified.strftime("%Y-%m-%d")
    if stdout:
        print("Removing: {0}  ({1})".format(path, date))
    else:
        LOG.info("Removing: %s  (%s)", path, date)


def prune(path, days, dry_run=False, stdout=False):
    """
    Recursively go through the results directory and remove all stored SRPM
    packages, that are too old.
    """
    path = os.path.normpath(path)
    too_old = datetime.now() - timedelta(days=days)
    for root, subdirs, files in walk_limited(path, mindepth=3, maxdepth=3):
        parsed = os.path.normpath(root).split(os.sep)

        if parsed[-1] != "srpm-builds":
            continue

        for subdir in subdirs:
            subdir = os.path.join(root, subdir)
            modified = datetime.fromtimestamp(os.path.getmtime(subdir))

            if modified >= too_old:
                continue

            print_remove_text(subdir, modified, stdout)
            if not dry_run:
                shutil.rmtree(subdir)

        # We don't create such files anymore but it doesn't hurt to check
        for srpm_log_file in files:
            srpm_log_file = os.path.join(root, srpm_log_file)

            if not srpm_log_file.endswith(".log"):
                continue

            modified = datetime.fromtimestamp(os.path.getmtime(srpm_log_file))
            print_remove_text(srpm_log_file, modified, stdout)
            if not dry_run:
                os.remove(srpm_log_file)


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
