import json

import flask
from flask import make_response

from coprs.exceptions import CoprHttpException


api_ns = flask.Blueprint("api_ns", __name__, url_prefix="/api")


def error_response(error):
    """

    :type error: CoprHttpException
    :return:
    """
    body = {
        "error": error.message,
        "output": "notok"
    }
    if error.kwargs:
        body.update(error.kwargs)
    resp = make_response(json.dumps(body), error.code)
    resp.mimetype = "application/json"

    return resp


@api_ns.errorhandler(CoprHttpException)
def handle_api_errors(error):
    return error_response(error)


