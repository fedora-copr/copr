# coding: utf-8

import fcntl
import os
from contextlib import contextmanager

@contextmanager
def file_lock(lock_file):
    if not os.path.isfile(lock_file):
        with open(lock_file, "w") as fd:
            fd.write("1")
    with open(lock_file, "r") as fd:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
