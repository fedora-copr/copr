"""
Red Hat subscription
"""

from fnmatch import fnmatch


def subscription_required(chroot, patterns):
    """
    Is subscription required for this task?
    """
    for pattern in patterns:
        if fnmatch(chroot, pattern):
            return True
    return False
