from flask import Response

from . import app


class BadRequestException(Exception):
    status_code = 400


class GpgErrorException(Exception):
    status_code = 500


@app.errorhandler(BadRequestException)
def handle_invalid_usage(error):
    response = Response(error.message, content_type="text/plain;charset=UTF-8")
    response.status_code = error.status_code
    return response
