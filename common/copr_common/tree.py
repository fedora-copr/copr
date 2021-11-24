"""
Common Copr code for working with directories and their contents
"""

import os


def walk_limited(path, maxdepth=None, mindepth=None):
    """
    The same as os.walk(), except that we can control the returned values to
    minimal and maximal depth of traversed directories.  The maximum depth is
    also lowering I/O because we don't actually have to traverse whole tree of
    unused files.
    """
    for dirpath, dirnames, files in os.walk(path):
        raw_subpath = os.path.relpath(dirpath, path)
        subpath = os.path.normpath(raw_subpath)
        depth = 0
        if subpath != ".":
            depth = len(subpath.split(os.sep))
        old_dirnames = dirnames.copy()
        if maxdepth is not None and depth >= maxdepth:
            # Per help(os.walk), we don't want to go deeper:
            # ...
            # When topdown is true, the caller can modify the dirnames list
            # in-place (e.g., via del or slice assignment), and walk will only
            # recurse into the subdirectories whose names remain in dirnames;
            # ...
            del dirnames[:]
        if mindepth is None or depth >= mindepth:
            yield dirpath, old_dirnames, files
