#!/usr/bin/python3
# coding: utf-8

import os
import sys
import argparse
import logging

from copr_dist_git.helpers import ConfigReader
from copr_dist_git.importer import Importer

log = logging.getLogger(__name__)


def get_arg_parser():
    """
    Parser for commandline options
    """
    description = "copr-dist-git process for importing packages"
    parser = argparse.ArgumentParser("importer_runner", description=description)
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run this process on foreground, using just a single thread",
    )
    parser.add_argument(
        "config",
        help="Path to a config file",
        nargs="?",
    )
    return parser


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

    config_reader = ConfigReader(args.config)
    try:
        opts = config_reader.read()
    except Exception:
        print("Failed to read config file, used file location: `{}`"
              .format(config_file))
        sys.exit(1)

    if args.foreground:
        opts.multiple_threads = False

    logging.basicConfig(
        filename=os.path.join(opts.log_dir, "main.log"),
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d][pid:%(process)d] %(message)s',
        datefmt='%H:%M:%S'
    )

    logging.getLogger('requests.packages.urllib3').setLevel(logging.WARN)
    logging.getLogger('urllib3').setLevel(logging.WARN)

    log.info("Make sure per-task-logs dir exists at: {}".format(opts.per_task_log_dir))
    try:
        os.makedirs(opts.per_task_log_dir)
    except OSError:
        if not os.path.isdir(opts.per_task_log_dir):
            log.error("Could not create per-task-logs directory at path {}"
                      .format(opts.per_task_log_dir))
            sys.exit(1)

    log.info("Logging configuration done")
    log.info("Using configuration: \n"
             "{}".format(opts))
    importer = Importer(opts)
    try:
        importer.run()
    except:
        log.exception("Unexpected exception raised")


if __name__ == "__main__":
    main()
