# coding: utf-8

import flask

from coprs.views.misc import page_not_found, access_restricted, bad_request_handler, server_error_handler
from coprs.exceptions import ObjectNotFound, AccessRestricted, BadRequest, CoprHttpException

coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")


@coprs_ns.errorhandler(ObjectNotFound)
def handle_404(error):
    return page_not_found(error.message)


@coprs_ns.errorhandler(AccessRestricted)
def handle_403(error):
    return access_restricted(error.message)


@coprs_ns.errorhandler(BadRequest)
def handle_400(error):
    return bad_request_handler(error.message)


@coprs_ns.errorhandler(CoprHttpException)
def handle_500(error):
    return server_error_handler(error.message)
