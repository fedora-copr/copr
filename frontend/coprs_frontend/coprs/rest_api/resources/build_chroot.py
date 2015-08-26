# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint

from ... import models
from coprs.exceptions import MalformedArgumentException
from coprs.logic.builds_logic import BuildsLogic, BuildChrootsLogic
from coprs.rest_api.exceptions import MalformedRequest
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema, BuildChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one


def render_build_chroot(chroot):
    """
    :type chroot: models.BuildChroot
    """
    return {
        "chroot": mm_serialize_one(BuildChrootSchema, chroot),
        "_links": {
            "project": {"href": url_for(".projectr", project_id=chroot.build.copr_id)},
            "self": {"href": url_for(".buildchrootr",
                                     build_id=chroot.build.id,
                                     name=chroot.name)},
        }
    }


class BuildChrootListR(Resource):
    def get(self, build_id):
        build = get_one_safe(BuildsLogic.get(build_id),
                             "Build {} Not found".format(build_id))

        return {
            "chroots": [
                render_build_chroot(chroot)
                for chroot in build.build_chroots
            ],
            "_links": {
                "self": {"href": url_for(".buildchrootlistr", build_id=build_id)}
            }
        }


class BuildChrootR(Resource):

    @staticmethod
    def _get_chroot_safe(build_id, name):
        try:
            chroot = get_one_safe(
                BuildChrootsLogic.get_by_build_id_and_name(build_id, name),
                "Build chroot {} for build {} not found"
            )
        except MalformedArgumentException as err:
            raise MalformedRequest("Bad mock chroot name: {}".format(err))
        return chroot

    def get(self, build_id, name):
        chroot = self._get_chroot_safe(build_id, name)
        return render_build_chroot(chroot)

    # todo: add put method: allows only to pass status: cancelled to cancel build

