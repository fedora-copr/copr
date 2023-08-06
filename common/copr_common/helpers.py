"""
Helper methods that can be used by any part of the Copr stack.  Typically small
things that don't need to have it's own file.
"""

import os
import pwd
import sys

def script_requires_user(username):
    """
    Exit if the current system user name doesn't equal to the USERNAME argument.
    """
    actual_username = pwd.getpwuid(os.getuid())[0]
    if actual_username != username:
        msg = (
            "This script should be executed "
            "as '{0}' user, not '{1}'\n"
        ).format(
            username,
            actual_username,
        )
        sys.stderr.write(msg)
        sys.exit(1)


def chroot_to_branch(chroot):
    """
    Get a git branch name from chroot. Follow the fedora naming standard.
    """
    name, version, _arch = chroot.rsplit("-", 2)
    if name == "fedora":
        if version == "rawhide":
            return "master"
        abbrev = "f"
    elif name == "epel" and int(version) <= 6:
        abbrev = "el"
    elif name == "mageia" and version == "cauldron":
        abbrev = "cauldron"
        version = ""
    elif name == "mageia":
        abbrev = "mga"
    return "{}{}".format(abbrev, version)
