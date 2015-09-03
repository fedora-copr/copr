# coding: utf-8

from flask import url_for
from flask_restful import Resource

from coprs.rest_api.common import render_build_chroot
from ...exceptions import MalformedArgumentException
from ...logic.builds_logic import BuildsLogic, BuildChrootsLogic
from ..exceptions import MalformedRequest
from ..util import get_one_safe


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

