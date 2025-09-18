"""
Helper methods that can be used by any part of the Copr stack.  Typically small
things that don't need to have it's own file.
"""

import contextlib
import os
import pwd
import sys


# When build is resubmitted with user SSH,
# how long the builder is kept alive if user doesn't prolong it (in seconds).
USER_SSH_DEFAULT_EXPIRATION = 60 * 60

# When build is resubmitted with user SSH,
# how long the builder can be prolonged to be kept alive (in seconds).
USER_SSH_MAX_EXPIRATION = 60 * 60 * 24 * 3

# When build is resubmitted with user SSH,
# in what file the expiration timestamp should be stored
USER_SSH_EXPIRATION_PATH = "/run/copr-builder-expiration"


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
    abbrev = name
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


def timedelta_to_dhms(delta):
    """
    By default the `datetime.timedelta` provides only days and seconds. Minutes,
    hours, and the human friendly number of seconds, needs to be calculated.
    """
    days, remainder = divmod(delta.total_seconds(), 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    return int(days), int(hours), int(minutes), int(seconds)


@contextlib.contextmanager
def nullcontext():
    """
    contextlib.nullcontext is not available in Python 3.6, but we are still
    Python 3.6+ compatible because of EL 8
    """
    yield None
