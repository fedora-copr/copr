"""
A place for exception-handling logic
"""

import logging
from functools import partial

import flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException, NotFound, GatewayTimeout
from coprs.exceptions import CoprHttpException

LOG = logging.getLogger(__name__)


def generic_error(message, code=500, title=None, headers=None):
    """
    :type message: str
    :type err: CoprHttpException
    """

    template = flask.render_template("html-error.html",
                                     message=message,
                                     error_code=code,
                                     error_title=title)
    retval = [template, code]
    if headers is not None:
        # custom headers needed
        retval.append(headers)
    return tuple(retval)


bad_request_handler = partial(generic_error, code=400, title="Bad Request")
conflict_request_handler = partial(generic_error, code=409, title="Conflict")
access_restricted = partial(generic_error, code=403, title="Access Restricted")
page_not_found = partial(generic_error, code=404, title="Page Not Found")
unprocessable_entity = partial(generic_error, code=422, title="Unprocessable Entity")


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

        This method is expected to be implemented in descendants of this class.
        """
        raise NotImplementedError

    def code(self, error):  # pylint: disable=no-self-use
        """
        Return status code for a given exception
        """
        code = getattr(error, "code", 500)
        return code if code is not None else 500


    def message(self, error):  # pylint: disable=no-self-use
        """
        Return an error message for a given exception. We want to obtain messages
        differently for `CoprHttpException`, `HTTPException`, or others.
        """
        if isinstance(error, HTTPException):
            return error.description
        return str(error)

    def _log_admin_only_exception(self):
        # pylint: disable=no-self-use
        LOG.exception("Admin-only exception\nRequest: %s %s\nUser: %s\n",
                      flask.request.method,
                      flask.request.url,
                      flask.g.user.name if flask.g.user else None)


class UIErrorHandler(BaseErrorHandler):
    """
    Handle exceptions raised from the web user interface
    """

    def handle_error(self, error):
        code = self.code(error)
        message = self.message(error)
        headers = getattr(error, "headers", None)

        # The most common error has their own custom error pages. When catching
        # a new exception, try to keep it simple and just the the generic one.
        # Create it's own view only if necessary.
        error_views = {
            400: bad_request_handler,
            403: access_restricted,
            404: page_not_found,
            409: conflict_request_handler,
            422: unprocessable_entity,
        }
        if code in error_views:
            return error_views[code](message, headers=headers)

        message = "Server error, contact admin"
        if isinstance(error, SQLAlchemyError):
            code = 500
            message = "Database error, contact admin"

        self._log_admin_only_exception()
        return generic_error(message, code)


class APIErrorHandler(BaseErrorHandler):
    """
    Handle exceptions raised from API (v3)
    """

    def handle_error(self, error):
        code = self.code(error)
        message = self.message(error)

        # In the majority of cases, we want to return the message that was
        # passed through an exception, but occasionally we want to redefine the
        # message to some API-related one. Please try to keep it simple and
        # do this only if necessary.
        errors = {
            NotFound: "Such API endpoint doesn't exist",
            GatewayTimeout: "The API request timeouted",
        }
        if error.__class__ in errors:
            message = errors[error.__class__]

        # Every `CoprHttpException` and `HTTPException` failure has valuable
        # message for the end user. It holds information that e.g. some value is
        # missing or incorrect, something cannot be done, something doesn't
        # exist. Eveything else should really be an uncaught exception caused by
        # either not properly running all frontend requirements (PostgreSQL,
        # Redis), or having a bug in the code.
        if not any([isinstance(error, CoprHttpException),
                    isinstance(error, HTTPException)]):
            message = ("Request wasn't successful, "
                       "there is probably a bug in the API code.")
        self._log_admin_only_exception()
        return self.respond(message, code)

    def respond(self, message, code):  # pylint: disable=no-self-use
        """
        Return JSON response suitable for API clients
        """
        response = flask.jsonify(error=message)
        response.status_code = code
        return response
