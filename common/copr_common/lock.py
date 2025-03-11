"""
File locking for multithreading
"""

import os
import contextlib
import filelock
from setproctitle import getproctitle, setproctitle


@contextlib.contextmanager
def lock(path, lockdir, timeout, log):
    """
    Create a lock file that can be accessed only by one thread at the time.
    A practical use-case for this is to lock a repository so multiple versions
    of the same package cannot be imported in paralel.

    We want to pass a simple `path` parameter specifying what file or directory
    should be locked. This however isn't where the lockfile is going to be
    created. It will be created in the `lockdir`.

    From FileLock docs:
    Using a timeout < 0 makes the lock block until it can be acquired while
    timeout == 0 results in only one attempt to acquire the lock before raising
    a Timeout exception (-> non-blocking).
    """
    filename = path.replace("/", "_@_") + ".lock"
    lockfile = os.path.join(lockdir, filename)

    title = getproctitle()
    setproctitle("{0} [locking]".format(title))
    log.debug("acquiring lock")
    try:
        with filelock.FileLock(lockfile, timeout=timeout):
            setproctitle("{0} [locked]".format(title))
            log.debug("acquired lock")
            yield
    except filelock.Timeout as err:
        log.debug("lock timeouted")
        raise LockTimeout("Timeouted on lock for: {}".format(path)) from err
    finally:
        setproctitle("{0} [locking]".format(title))


class LockTimeout(OSError):
    """
    Raised for lock() timeout, if timeout= option is set to value >= 0
    """
