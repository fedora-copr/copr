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
