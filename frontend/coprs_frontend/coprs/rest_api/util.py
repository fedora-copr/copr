# coding: utf-8
import json

import sqlalchemy.orm.exc
from .exceptions import ObjectNotFoundError, MalformedRequest
from schemas import AllowedMethodSchema
from flask import Response, url_for, Blueprint


class AllowedMethod(object):
    def __init__(self, method, doc, require_auth=True, params=None):
        self.method = method
        self.doc = doc
        self.require_auth = require_auth
        self.params = params or []


def render_allowed_method(method, doc, require_auth=True, params=None):
    return AllowedMethodSchema().dump(AllowedMethod(method, doc, require_auth, params))[0]


def get_one_safe(query, data_on_error=None):
    try:
        return query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise ObjectNotFoundError(data_on_error)


def json_loads_safe(raw, data_on_error=None):
    try:
        return json.loads(raw)
    except ValueError:
        raise MalformedRequest(data_on_error or
                               "Failed to deserialize json string")


def mm_deserialize(schema, json_string):
    try:
        result = schema.loads(json_string)
    except ValueError as err:
        raise MalformedRequest(data="Failed to parse request: {}"
                               .format(err))

    if result.errors:
        raise MalformedRequest(data="Failed to parse request: {}"
                               .format(result.errors))

    return result


def mm_serialize_one(schema, obj):
    return schema().dump(obj)[0]
