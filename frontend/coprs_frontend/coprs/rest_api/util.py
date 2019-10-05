# coding: utf-8
import json

import sqlalchemy.orm.exc

from flask_restful.reqparse import Argument, RequestParser

from marshmallow.exceptions import ValidationError
from .exceptions import ObjectNotFoundError, MalformedRequest
from .schemas import AllowedMethodSchema


class AllowedMethod(object):
    def __init__(self, method, doc, require_auth=True, params=None):
        self.method = method
        self.doc = doc
        self.require_auth = require_auth
        self.params = params or []


def render_allowed_method(method, doc, require_auth=True, params=None):
    method = AllowedMethod(method, doc, require_auth, params)
    return mm_serialize_one(AllowedMethodSchema, method)


def get_one_safe(query, msg=None, data=None):
    """
    :type query:  sqlalchemy.Query
    :param str msg: message used in error when object not found
    :param Any data: any serializable data to include into error
    :raises ObjectNotFoundError: when query failed to return anything
    """
    try:
        return query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise ObjectNotFoundError(msg=msg, data=data)


def json_loads_safe(raw, data_on_error=None):
    try:
        return json.loads(raw)
    except ValueError:
        raise MalformedRequest(data_on_error or
                               "Failed to deserialize json string")


def mm_deserialize(schema, json_string):
    try:
        return schema.loads(json_string)
    except (ValueError, ValidationError) as err:
        raise MalformedRequest(
            msg="Failed to parse request: {}".format(err),
            data={"request_string": json_string}
        )

def mm_serialize_one(schema, obj):
    try:
        return schema().dump(obj)
    except ValidationError as err:
        # This isn't correct behavior, but we used to ignore ValidationError
        # before (e.g rhbz#1758559) and there's no desire to fix APIv2 when
        # there's APIv3.
        pass


class MyArg(Argument):
    def handle_validation_error(self, error, bundle_errors):
        # dirty monkey patching, better to switch to webargs
        # bundle errors are ignored
        data = {u"error": str(error)}
        if self.help:
            data["help"] = self.help
        raise MalformedRequest(
            "Failed to validate query parameter: {}".format(self.name),
            data=data
        )


def get_request_parser():
    return RequestParser(argument_class=MyArg)


def arg_bool(value):
    """
    :param str value: value to convert
    :rtype: bool
    :raises ValueError:
    """
    true_values = ["true", "yes", "1"]
    false_values = ["false", "no", "0"]
    value = str(value).strip().lower()

    if value in true_values:
        return True
    elif value in false_values:
        return False

    raise ValueError("Value `{}` doesn't belong to either true of false sets. "
                     "Allowed values: {} and {}"
                     .format(value, true_values, false_values))
