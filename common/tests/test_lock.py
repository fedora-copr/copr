"""
Test fcntl.flock fairness: processes blocked on the lock are served in FIFO order.
"""

import logging
import os
import shutil
import tempfile
import time

from copr_common.lock import lock

CONCURRENCY = 8
MAX_WAIT_AFTER_RELEASE = 2  # seconds


def test_lock_fairness():
    workdir = tempfile.mkdtemp(prefix="copr-test-lock-")
    lockdir = os.path.join(workdir, "locks")
    result_file = os.path.join(workdir, "order.log")
    log = logging.getLogger("test_lock_fairness")

    children = []
    try:
        with lock("/test-fairness", lockdir=lockdir, log=log):
            for i in range(CONCURRENCY):
                pid = os.fork()
                if pid == 0:
                    with lock("/test-fairness", lockdir=lockdir, log=log):
                        fd = os.open(result_file,
                                     os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                     0o644)
                        os.write(fd, "{}\n".format(i).encode())
                        os.close(fd)
                    os._exit(0)
                children.append(pid)
                time.sleep(0.05)

            # let all children reach the flock() call
            time.sleep(2)

            # all children should be alive, blocked on the lock
            for pid in children:
                result, _ = os.waitpid(pid, os.WNOHANG)
                assert result == 0, \
                    "child {} exited prematurely while lock is held".format(pid)

        # wait for all children, with a timeout
        deadline = time.monotonic() + MAX_WAIT_AFTER_RELEASE
        remaining = set(children)
        while remaining:
            assert time.monotonic() < deadline, \
                "children did not finish within {}s".format(MAX_WAIT_AFTER_RELEASE)
            for pid in list(remaining):
                result, status = os.waitpid(pid, os.WNOHANG)
                if result != 0:
                    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, \
                        "child {} exited with status {}".format(pid, status)
                    remaining.discard(pid)
                    children.remove(pid)

        with open(result_file) as f:
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
