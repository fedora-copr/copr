# coding: utf-8

import flask

from coprs.views.misc import (
    generic_error,
    access_restricted,
    bad_request_handler,
    conflict_request_handler,
    page_not_found,
    server_error_handler,
)

from coprs.exceptions import CoprHttpException

coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")


class UIErrorHandler(object):
    def handle_error(self, error):
        # The most common error has their own custom error pages. When catching
        # a new exception, try to keep it simple and just the the generic one.
        # Create it's own view only if necessary.
        error_views = {
            400: bad_request_handler,
            403: access_restricted,
            404: page_not_found,
            409: conflict_request_handler,
        }
        message = self.message(error)
        if error.code in error_views:
            return error_views[error.code](message)
        return generic_error(self.message(error), error.code)

    def message(self, error):
        if isinstance(error, CoprHttpException):
            return error.message or error._default
        if hasattr(error, "description"):
            return error.description
        return str(error)
