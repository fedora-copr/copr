#! /usr/bin/python3

"""
Testing background action spawner.
"""

import os
import sys
import time
import daemon
from munch import Munch
import logging

WORKDIR = os.path.dirname(__file__)

sys.path.append(os.path.join(WORKDIR, '..'))

# pylint: disable=wrong-import-position
from copr_common.redis_helpers import get_redis_connection

REDIS_OPTS = Munch(
    redis_db=9,
    redis_port=7777,
)

def do_the_useful_stuff(process_counter, task_id, worker_id, sleep):
    """
    Execute the testing code as background daemon.

    There are several environment variables which can be set by the testing
    WorkerManager:

    'FAIL_EARLY': When set, nothing happens, the worker doesn't even mark
        itself as starting in Redis DB.
    'FAIL_STARTED_PID': Process ends immediately after marked as starting, but
        before setting 'PID' in Redis DB
    'FAIL_STARTED: When set, 'started' and 'PID' Redis fields are set, but
        then we fail.  Before we actually start doing anything "useful".

    When none of those environment variables are set, we process to do the work
    (sleep) according to the ``sleep`` argument.  We set 'status' according to
    the ``process_counter`` (each 8th is failure).
    """
    if 'FAIL_EARLY' in os.environ:
        raise Exception("sorry")

    redis = get_redis_connection(REDIS_OPTS)

    redis.hset(worker_id, 'started', 1)

    if 'FAIL_STARTED_PID' in os.environ:
        return 0

    redis.hset(worker_id, 'PID', os.getpid())

    if 'FAIL_STARTED' in os.environ:
        raise Exception("sorry")

    # do some work!
    time.sleep(sleep)

    result = 1 if process_counter % 8 else 2
    redis.hset(worker_id, 'status', str(result))
    return 0


if __name__ == "__main__":
    with daemon.DaemonContext():
        do_the_useful_stuff(int(sys.argv[1]), sys.argv[2], sys.argv[3],
                            float(sys.argv[4]))
