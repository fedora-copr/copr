"""
Test fair (FIFO) Redis-based locking: processes blocked on the lock
are served in the order they enqueued.
"""

import logging
import os
import shutil
import tempfile
import time

from redis import StrictRedis

from copr_common.lock import lock

CONCURRENCY = 8
MAX_WAIT = 10  # seconds

log = logging.getLogger("test_lock_fairness")


def _get_redis():
    return StrictRedis(
        host="127.0.0.1",
        port=7777,
        db=9,
        encoding="utf-8",
        decode_responses=True,
    )


def _cleanup_keys(redis_conn, path):
    for prefix in ["copr:lock:queue:", "copr:lock:notify:"]:
        for key in redis_conn.keys(prefix + path + "*"):
            redis_conn.delete(key)


def test_lock_fairness():
    redis_conn = _get_redis()
    lock_name = "/test-fairness"
    _cleanup_keys(redis_conn, lock_name)

    workdir = tempfile.mkdtemp(prefix="copr-test-lock-")
    result_file = os.path.join(workdir, "order.log")

    children = []
    try:
        with lock(lock_name, redis_conn=redis_conn, log=log):
            for i in range(CONCURRENCY):
                pid = os.fork()
                if pid == 0:
                    child_redis = _get_redis()
                    with lock(lock_name, redis_conn=child_redis, log=log):
                        fd = os.open(result_file,
                                     os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                     0o644)
                        os.write(fd, "{}\n".format(i).encode())
                        os.close(fd)
                    os._exit(0)
                children.append(pid)
                time.sleep(0.05)

            time.sleep(2)

            assert not os.path.exists(result_file), \
                "result file should not exist yet while parent holds the lock"

            for pid in children:
                result, _ = os.waitpid(pid, os.WNOHANG)
                assert result == 0, \
                    "child {} exited prematurely while lock is held".format(pid)

        deadline = time.monotonic() + MAX_WAIT
        remaining = set(children)
        while remaining:
            assert time.monotonic() < deadline, \
                "children did not finish within {}s".format(MAX_WAIT)
            for pid in list(remaining):
                result, status = os.waitpid(pid, os.WNOHANG)
                if result != 0:
                    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, \
                        "child {} exited with status {}".format(pid, status)
                    remaining.discard(pid)
                    children.remove(pid)
            time.sleep(0.1)

        with open(result_file, encoding="utf-8") as f:
            order = [int(line.strip()) for line in f]

        assert order == list(range(CONCURRENCY)), \
            "expected FIFO order {}, got {}".format(
                list(range(CONCURRENCY)), order)
    finally:
        for pid in children:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except OSError:
                pass
        shutil.rmtree(workdir, ignore_errors=True)
        _cleanup_keys(redis_conn, lock_name)


def test_lock_dead_process_cleanup():
    """
    Simulate a dead lock holder by inserting a non-existent PID into the
    Redis queue.  The next lock() caller should detect the dead PID via
    kill(pid, 0) → ESRCH, remove the stale entry from the queue, and
    successfully acquire the lock without waiting for the BLPOP timeout.
    """
    redis_conn = _get_redis()
    lock_name = "/test-dead-cleanup"
    _cleanup_keys(redis_conn, lock_name)

    try:
        # Insert a PID that definitely doesn't exist — this is what happens
        # when a lock holder dies (kill -9, OOM, etc.) without running the
        # finally block that would LPOP its entry.
        dead_pid = "999999999"
        queue_key = "copr:lock:queue:{}".format(lock_name)
        redis_conn.rpush(queue_key, dead_pid)

        # lock() should detect the dead PID at the head of the queue,
        # remove it, and let us through.
        acquired = False
        with lock(lock_name, redis_conn=redis_conn, log=log):
            acquired = True
        assert acquired
    finally:
        _cleanup_keys(redis_conn, lock_name)
