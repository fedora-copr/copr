# coding: utf-8

import flask

from coprs.views.misc import page_not_found, access_restricted, bad_request_handler, server_error_handler
from coprs.exceptions import CoprHttpException

coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")


class UIErrorHandler(object):
    def handle_404(self, error):
        return page_not_found(self.message(error))

    def handle_403(self, error):
        return access_restricted(self.message(error))

    def handle_400(self, error):
        return bad_request_handler(self.message(error))

    def handle_500(self, error):
        return server_error_handler(self.message(error))

    def handle_504(self, error):
        return server_error_handler(self.message(error))

    def message(self, error):
        if isinstance(error, CoprHttpException):
            return error.message
        if hasattr(error, "description"):
            return error.description
        return str(error)
