#!/usr/bin/python2
# coding: utf-8

import os
import sys
import logging

from dist_git.helpers import DistGitConfigReader
from dist_git.dist_git_importer import DistGitImporter

log = logging.getLogger(__name__)


def main():
    config_file = None

    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    config_reader = DistGitConfigReader(config_file)
    try:
        opts = config_reader.read()
    except Exception:
        print("Failed to read config file, used file location: `{}`"
              .format(config_file))
        # sys.exit(1)
        sys.exit(1)

    logging.basicConfig(
        filename=os.path.join(opts.log_dir, "main.log"),
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d] %(message)s',
        datefmt='%H:%M:%S'
    )

    logging.getLogger('requests.packages.urllib3').setLevel(logging.WARN)
    logging.getLogger('urllib3').setLevel(logging.WARN)

    log.info("Logging configuration done")
    log.info("Using configuration: \n"
             "{}".format(opts))
    importer = DistGitImporter(opts)
    importer.run()


if __name__ == "__main__":
    main()
