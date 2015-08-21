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


class MockChrootListR(Resource):
    def get(self):
        # todo: add argument active_only
        chroots = MockChrootsLogic.get_multiple(active_only=False).all()
        return {
            "_links": {
                "self": {"href": url_for(".mockchrootlistr")},
            },
            "chroots": [
                {
                    "chroot": MockChrootSchema().dump(chroot)[0],
                    "_links": {
                        "self": {"href": url_for(".mockchrootr", name=chroot.name)},
                    }
                } for chroot in chroots
            ]
        }


class MockChrootR(Resource):
    def get(self, name):
        chroot = get_one_safe(MockChrootsLogic.get_from_name(name))
        return {
            "chroot": MockChrootSchema().dump(chroot)[0],
            "_links": {
                "self": {"href": url_for(".mockchrootr", name=chroot.name)},
                "all_chroots": {"href": url_for(".mockchrootlistr")}
            },
        }


class CoprChrootListR(Resource):
    pass


class CoprChrootR(Resource):
    pass
