# pylint: disable=R0903
# coding: utf-8
from copr.util import UnicodeMixin


class EntityTypes(object):
    ROOT = "root"
    PROJECT = "project"
    PROJECT_CHROOT = "project_chroot"
    BUILD = "build"
    BUILD_TASK = "build_task"
    MOCK_CHROOT = "mock_chroot"


class BuiltPackage(UnicodeMixin):

    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __unicode__(self):
        return u"{0} {1}".format(self.name, self.version)


class BuildStateValues(object):
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    RUNNING = "running"
    PENDING = "pending"
    SKIPPED = "skipped"
    STARTING = "starting"
    IMPORTING = "importing"
    FORKED = "forked"
    WAITING = "waiting"
    UNKNOWN = "unknown"

ALLOWED_BUILD_STATES = set([
    BuildStateValues.FAILED,
    BuildStateValues.SUCCEEDED,
    BuildStateValues.CANCELED,
    BuildStateValues.RUNNING,
    BuildStateValues.PENDING,
    BuildStateValues.SKIPPED,
    BuildStateValues.STARTING,
    BuildStateValues.IMPORTING,
    BuildStateValues.FORKED,
    BuildStateValues.WAITING,
    BuildStateValues.UNKNOWN,
])
