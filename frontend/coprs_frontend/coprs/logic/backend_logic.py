# coding: utf-8

import json
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.sql import false

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers

from coprs.logic.coprs_logic import MockChrootsLogic

log = app.logger


class BackendLogic(object):
    @classmethod
    def build_version_already_done(cls, build, chroot_name, version):
        pkg = build.package
        mock_chroot = MockChrootsLogic.get_from_name(chroot_name)
        query = (models.Build.query
                 .join(models.BuildChroot)
                 .filter(models.Build.package_id == pkg.id)
                 .filter(models.Build.version == version)
                 .filter(models.BuildChroot.mock_chroot_id == mock_chroot.id)
        )
        return len(query.all()) > 0
