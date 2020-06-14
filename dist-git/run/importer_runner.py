#!/usr/bin/python3
# coding: utf-8

import os
import sys
import logging

from dist_git.helpers import ConfigReader
from dist_git.importer import Importer

log = logging.getLogger(__name__)


def main():
    config_file = None

    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    config_reader = ConfigReader(config_file)
    try:
        opts = config_reader.read()
    except Exception:
        print("Failed to read config file, used file location: `{}`"
              .format(config_file))
        sys.exit(1)

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
