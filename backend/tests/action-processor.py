#! /usr/bin/python3

import os
import sys
import time
import daemon
from munch import Munch
import logging

WORKDIR = os.path.dirname(__file__)

sys.path.append(os.path.join(WORKDIR, '..'))

from backend.helpers import get_redis_connection

REDIS_OPTS = Munch(
    redis_db=9,
    redis_port=7777,
)

def do_the_useful_stuff(process_counter, task_id, worker_id, sleep):
    if 'FAIL_EARLY' in os.environ:
        raise Exception("sorry")

    redis = get_redis_connection(REDIS_OPTS)

    redis.hset(worker_id, 'started', 1)
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
