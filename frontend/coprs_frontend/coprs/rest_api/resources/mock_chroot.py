# coding: utf-8

import json
import flask
from flask import url_for
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint
from coprs.rest_api.schemas import MockChrootSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize


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
