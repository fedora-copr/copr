"""
A place for exception-handling logic
"""

import flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import (
    ClientDisconnected,
    GatewayTimeout,
    HTTPException,
    NotFound,
)
from coprs import app
from coprs.exceptions import CoprHttpException


def get_error_handler():
    """
    Determine what error handler should be used for this request
    See http://flask.pocoo.org/docs/1.0/blueprints/#error-handlers
    """
    path = flask.request.path
    if path.startswith('/api_3/') and "gssapi_login/web-ui" not in path:
        return APIErrorHandler()
    return UIErrorHandler()


class BaseErrorHandler:
    """
    Do not use this class for handling errors. It is only a parent class for
    the actual error-handler classes.
    """
    def handle_error(self, error):
        """
        Return a flask response suitable for the current situation (e.g. reder
        HTML page for UI failures, send JSON back to API client, etc).
        """
        code = self.code(error)
        message = self.message(error)
        headers = getattr(error, "headers", None)
        message = self.override_message(message, error)
        app.logger.error("Response error: %s %s", code, message)
        return self.render(message, code), code, headers

    @staticmethod
    def render(message, code):
        """
        Using the message and code, generate the appropriate error page content.
        """
        raise NotImplementedError

    def override_message(self, message, error):
        """
        For particular sub-class, it may be desired to override/reformat the
        message for particular error.  This method should be overridden then.
        """
        _used_in_subclass = self, error
        return message

    @staticmethod
    def code(error):
        """
        Return status code for a given exception
        """
        code = getattr(error, "code", 500)
        return code if code is not None else 500

    def message(self, error):
        """
        Return an error message for a given exception. We want to obtain messages
        differently for `CoprHttpException`, `HTTPException`, or others.
        """
        message = "Unknown problem"

        # Every `CoprHttpException` and `HTTPException` failure has a valuable
        # message for the end user.  It holds information that e.g. some value
        # is missing or incorrect, something cannot be done, something doesn't
        # exist.
        if isinstance(error, HTTPException):
            message = error.description
            if isinstance(error, ClientDisconnected):
                message = "Client disconnected: " + message
            return message

        if isinstance(error, CoprHttpException):
            return str(error)

        # Everything else would normally be an uncaught exception caused by
        # either not properly running all frontend requirements (PostgreSQL,
        # Redis), or having a bug in the code.  For such cases we try to do
        # our best to identify the failure reason (but we stay with
        # error_code=500).
        message = ("Request wasn't successful, "
                   "there is probably a bug in the Copr code.")
        if isinstance(error, SQLAlchemyError):
            message = "Database error, contact admin"
        self._log_admin_only_exception()
        return message

    def _log_admin_only_exception(self):
        # pylint: disable=no-self-use
        app.logger.exception("Admin-only exception\nRequest: %s %s\nUser: %s\n",
                             flask.request.method,
                             flask.request.url,
                             flask.g.user.name if flask.g.user else None)


class UIErrorHandler(BaseErrorHandler):
    """
    Handle exceptions raised from the web user interface
    """
    @staticmethod
    def render(message, code):
        title = {
            400: "Bad Request",
            409: "Conflict",
            403: "Access Restricted",
            404: "Page Not Found",
            422: "Unprocessable Entity",
        }.get(code, "Unknown error")
        return flask.render_template("html-error.html",
                                     message=message,
                                     error_code=code,
                                     error_title=title)


class APIErrorHandler(BaseErrorHandler):
    """
    Handle exceptions raised from API (v3)
    """
    def override_message(self, message, error):
        return {
            NotFound: "Such API endpoint doesn't exist",
            GatewayTimeout: "The API request timeouted",
        }.get(error.__class__, message)

    @staticmethod
    def render(message, code):
        return flask.jsonify(error=message)
