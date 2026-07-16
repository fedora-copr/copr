"""
File locking using fcntl.flock (blocking, fair via kernel wait queue)
"""

import contextlib
import fcntl
import os

from setproctitle import getproctitle, setproctitle


@contextlib.contextmanager
def lock(path, lockdir, log, timeout=None):
    """
    Create a lock file that can be accessed only by one thread at the time.
    A practical use-case for this is to lock a repository so multiple versions
    of the same package cannot be imported in paralel.

    We want to pass a simple `path` parameter specifying what file or directory
    should be locked. This however isn't where the lockfile is going to be
    created. It will be created in the `lockdir`.

    Uses blocking fcntl.flock(LOCK_EX), which is fair (kernel FIFO wait queue)
    and consumes zero CPU while waiting.
    """
    filename = path.replace("/", "_@_") + ".lock"
    lockfile = os.path.join(lockdir, filename)

    os.makedirs(lockdir, exist_ok=True)

    title = getproctitle()
    setproctitle("{0} [locking]".format(title))
    log.debug("acquiring lock")
    fd = os.open(lockfile, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        setproctitle("{0} [locked]".format(title))
        log.debug("acquired lock")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        setproctitle(title)
