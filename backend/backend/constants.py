import os

mockchain = "/usr/bin/mockchain"
# rsync path
rsync = "/usr/bin/rsync"

DEF_REMOTE_BASEDIR = "/var/tmp"
DEF_BUILD_TIMEOUT = 3600 * 6
DEF_REPOS = []
DEF_CHROOT = None
DEF_BUILD_USER = "mockbuilder"
DEF_DESTDIR = os.getcwd()
DEF_MACROS = {}
DEF_BUILDROOT_PKGS = ""


class BuildStatus(object):
    FAILURE = 0
    SUCCEEDED = 1
    SKIPPED = 5
