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


class ProjectChrootListR(Resource):
    pass


class ProjectChrootR(Resource):
    pass
