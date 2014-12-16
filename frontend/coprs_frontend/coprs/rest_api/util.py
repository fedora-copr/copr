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


def bp_url_for(endpoint, *args, **kwargs):
    """
        Prepend endpoing with dot
    :param endpoint:
    :param args:
    :param kwargs:
    :return:
    """

    return url_for(".{}".format(endpoint), *args, **kwargs)


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


def mm_deserialize(schema, obj_dict):
    result = schema.loads(obj_dict)
    if result.errors:
        raise MalformedRequest(data=result.errors)
    # import ipdb; ipdb.set_trace()
    return result
