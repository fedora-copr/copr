# coding: utf-8

from flask import url_for
from flask_restful import Resource

from ...logic.coprs_logic import MockChrootsLogic

from ..schemas import MockChrootSchema
from ..util import get_one_safe, get_request_parser, arg_bool, mm_serialize_one


def render_mock_chroot(chroot):
    return {
        "chroot": mm_serialize_one(MockChrootSchema, chroot),
        "_links": {
            "self": {"href": url_for(".mockchrootr", name=chroot.name)},
        },
    }


class MockChrootListR(Resource):

    @classmethod
    def get(cls):
        parser = get_request_parser()
        parser.add_argument('active_only', type=arg_bool)
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
    @classmethod
    def get(cls, name):
        chroot = get_one_safe(MockChrootsLogic.get_from_name(name))
        return render_mock_chroot(chroot)
