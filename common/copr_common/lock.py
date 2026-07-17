"""
Fair (FIFO) distributed locking using a Redis queue.

Waiters enqueue their PID and are served in arrival order.  Dead-process
detection uses kill(pid, 0) so no heartbeat thread is needed.
"""

import contextlib
import errno
import os

from setproctitle import getproctitle, setproctitle

BLPOP_TIMEOUT = 5  # seconds between dead-process checks


def _is_alive(pid):
    """Return True if *pid* refers to a running (non-zombie) process."""
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        if e.errno == errno.ESRCH:
            return False
        # EPERM → process exists but we lack permission
        return True


def _queue_key(path):
    return "copr:lock:queue:{}".format(path)


def _notify_key(path, pid):
    return "copr:lock:notify:{}:{}".format(path, pid)


@contextlib.contextmanager
def lock(path, redis_conn, log):
    """
    Fair (FIFO) distributed lock backed by a Redis list.

    Processes waiting for the lock are served in the order they called
    this function.  If the lock holder dies without releasing, the next
    waiter detects it via kill(pid, 0) and removes the stale entry.

    :param path:        Logical resource to lock (e.g. a repository path).
    :param redis_conn:  A ``redis.StrictRedis`` connection.
    :param log:         Logger instance.
    """
    queue = _queue_key(path)
    my_pid = os.getpid()
    my_pid_str = str(my_pid)
    notify = _notify_key(path, my_pid)

    title = getproctitle()
    setproctitle("{0} [locking]".format(title))
    log.debug("acquiring lock (fair/redis)")

    redis_conn.rpush(queue, my_pid_str)
    try:
        while True:
            head = redis_conn.lindex(queue, 0)
            if head is None:
                # Queue disappeared (e.g. Redis flushed) — re-enqueue.
                redis_conn.rpush(queue, my_pid_str)
                continue

            if head == my_pid_str:
                break

            head_pid = int(head)
            if not _is_alive(head_pid):
                log.debug("removing dead lock holder pid=%s", head)
                redis_conn.lrem(queue, 1, head)
                continue

            redis_conn.blpop(notify, timeout=BLPOP_TIMEOUT)

        setproctitle("{0} [locked]".format(title))
        log.debug("acquired lock (fair/redis)")
        yield

    finally:
        redis_conn.lpop(queue)
        next_pid = redis_conn.lindex(queue, 0)
        if next_pid is not None:
            redis_conn.rpush(_notify_key(path, next_pid), "1")
        redis_conn.delete(notify)
        setproctitle(title)
