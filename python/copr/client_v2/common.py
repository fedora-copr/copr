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
        return u"{} {}".format(self.name, self.version)
