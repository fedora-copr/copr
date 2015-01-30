#!/usr/bin/python -tt
# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import sys

from redis import StrictRedis

sys.path.append("/usr/share/copr/")


from backend.helpers import BackendConfigReader
from backend.constants import CONSECUTIVE_FAILURE_REDIS_KEY


def main():
    opts = BackendConfigReader().read()
    conn = StrictRedis()  # connecting to default local redis instance

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
