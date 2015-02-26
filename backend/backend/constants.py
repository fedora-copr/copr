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


DEF_CONSECUTIVE_FAILURE_THRESHOLD = 10
CONSECUTIVE_FAILURE_REDIS_KEY = "copr:sys:consecutive_build_fails"


class BuildStatus(object):
    FAILURE = 0
    SUCCEEDED = 1
    RUNNING = 3
    PENDING = 4
    SKIPPED = 5


JOB_GRAB_TASK_END_PUBSUB = "copr:backend:daemons:job_grab:task_end:pubsub::"
