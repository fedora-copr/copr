#!/usr/bin/python3 -tt
# coding: utf-8

import sys

from copr_backend.helpers import BackendConfigReader, get_redis_connection
from copr_backend.constants import CONSECUTIVE_FAILURE_REDIS_KEY


def main():
    opts = BackendConfigReader().read()
    conn = get_redis_connection(opts)

    key = CONSECUTIVE_FAILURE_REDIS_KEY

    value = int(conn.get(key) or 0)
    if value > opts.consecutive_failure_threshold:
        print("Critical")
        sys.exit(2)
    elif value > int(0.5 * opts.consecutive_failure_threshold):
        print("Warning")
        sys.exit(1)
    else:
        print("OK")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("UNKNOWN: {}".format(error))
        sys.exit(3)
