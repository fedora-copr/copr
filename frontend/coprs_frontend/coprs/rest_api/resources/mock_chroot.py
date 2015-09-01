# coding: utf-8

from flask import url_for
from flask_restful import Resource, reqparse

from ...logic.coprs_logic import MockChrootsLogic

from ..schemas import MockChrootSchema
from ..util import get_one_safe


def render_mock_chroot(chroot):
    return {
        "chroot": MockChrootSchema().dump(chroot)[0],
        "_links": {
            "self": {"href": url_for(".mockchrootr", name=chroot.name)},
            "all_chroots": {"href": url_for(".mockchrootlistr")}
        },
    }


class MockChrootListR(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('active_only', type=bool)
        req_args = parser.parse_args()
        active_only = False
        if req_args["active_only"]:
            active_only = True

        chroots = MockChrootsLogic.get_multiple(active_only=active_only).all()

        self_extra = {}
        if active_only:
            self_extra["active_only"] = active_only
        return {
            "_links": {
                "self": {"href": url_for(".mockchrootlistr", **self_extra)},
            },
            "chroots": [
                render_mock_chroot(chroot)
                for chroot in chroots
            ]
        }


class MockChrootR(Resource):
    def get(self, name):
        chroot = get_one_safe(MockChrootsLogic.get_from_name(name))
        return render_mock_chroot(chroot)
