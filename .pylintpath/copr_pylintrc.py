"""
Pylintrc initialization methods.
"""

import os
import sys
import subprocess

def init():
    """
    The main method, called in "init-hook=" config.
    """

    gitrootdir = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8").strip()

    # All modules depend, or can depend on python-common and python-copr
    sys.path.insert(0, os.path.join(gitrootdir, 'common'))
    sys.path.insert(0, os.path.join(gitrootdir, 'python'))
    gitsubdir = subprocess.check_output(["git", "rev-parse", "--show-prefix"]).decode("utf-8").strip()

    # Those sub-directories have the "nice" pattern, so setting the pythonpath
    # here is trivial.
    for nice_subdir in ["backend", "dist-git", "rpmbuild"]:
        if gitsubdir.startswith(nice_subdir):
            sys.path.insert(0, os.path.join(gitrootdir, nice_subdir))

    # Those still need a special handling (and in future file movements).
    if gitsubdir.startswith("frontend"):
        sys.path.insert(0, os.path.join(gitrootdir, "frontend", "coprs_frontend"))
    if gitsubdir.startswith("keygen"):
        sys.path.insert(0, os.path.join(gitrootdir, "keygen", "src"))
