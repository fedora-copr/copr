# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import json
import logging

from flask import Flask, request, Response
import os
from copr_keygen.exceptions import BadRequestException, \
    KeygenServiceBaseException
from copr_keygen.util import file_lock

app = Flask(__name__)
app.config.from_object("copr_keygen.default_settings")
app.config.from_envvar("COPR_KEYGEN_CONFIG", silent=True)


# setup logger
class RemoteAddrFilter(logging.Filter):
    """
    Define `%(remote_addr)s` key for the formatter string
    """

    def filter(self, record):
        record.remote_addr = request.remote_addr if request else "SERVER"
        return True


if not app.config["DEBUG"] or app.config["DEBUG_WITH_LOG"]:
    filename = os.path.join(app.config["LOG_DIR"], "main.log")
    if os.path.exists(app.config["LOG_DIR"]):
        handler = logging.FileHandler(filename)
        handler.setLevel(app.config["LOG_LEVEL"])
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s'
            '[%(module)s:%(pathname)s:%(lineno)d][%(remote_addr)s]'
            ': %(message)s '
        ))
        handler.addFilter(RemoteAddrFilter())
        app.logger.addHandler(handler)

    app.logger.setLevel(app.config["LOG_LEVEL"])
    app.logger.addFilter(RemoteAddrFilter())
# end setup logger


from .logic import create_new_key, user_exists, get_passphrase_location


@app.route('/ping')
def ping():
    """
    Checks if server still alive

    :status 200: server alive
    """
    app.logger.debug("got ping")
    return Response("pong\n", content_type="text/plain;charset=UTF-8")


@app.route('/gen_key', methods=["post"])
def gen_key():
    """
    Generates new key-pair

     **Example request**:

    .. sourcecode:: http

      POST /gen_key HTTP 1.1
      Content-Type: application/json

      {
        "name_real": "foo_bar",
        "name_email": "foo_bar@example.com"
      }


    request fields:
        - **name_real, name_email, name_comment**: for key identification
        - **key_length**: now supports 1024 or 2048 bytes
        - **expire**: [optional] key expire in days, default 0  means never

    :return: Http response with plain text content

    :status 201: on success, returns empty data
    :status 200: key already exists, nothing done
    :status 400: incorrect request
    :status 500: internal server error

    """
    try:
        charset = request.headers.get('charset', 'utf-8')
        query = json.loads(request.data.decode(charset))
    except Exception as e:
        raise BadRequestException("Failed to parse request body: {}".format(e))

    app.logger.info("received gen_key query: {}".format(query))
    if "name_real" not in query:
        raise BadRequestException("Request query missing required "
                                  "parameter `name_real`".format(query))

    if "name_email" not in query:
        raise BadRequestException("Request query missing required "
                                  "parameter `name_real`".format(query))

    name_email = query["name_email"]

    with file_lock(get_passphrase_location(app, name_email) + ".lock"):
        if user_exists(app, name_email):
            response = Response("", content_type="text/plain;charset=UTF-8")
            response.status_code = 200
            return response

        create_new_key(
            app,
            name_real=query["name_real"],
            name_email=name_email,
            name_comment=query.get("name_comment", None),
            key_length=query.get("key_length", app.config["GPG_KEY_LENGTH"]),
            expire=query.get("expire", app.config["GPG_EXPIRE"]),
        )

        response = Response("", content_type="text/plain;charset=UTF-8")
        response.status_code = 201
        return response


@app.errorhandler(500)
@app.errorhandler(KeygenServiceBaseException)
def handle_invalid_usage(error):
    response = Response(error.msg, content_type="text/plain;charset=UTF-8")
    response.status_code = error.status_code
    response.data = str(error)
    return response


# @app.route('/remove_key', methods=["post"])
# def remove_key():
#     raise NotImplementedError()
#     query = json.loads(request.data)
#     print(repr(query))
#     mail = query["name_email"]
#     #cmd = "gpg --with-colons --fingerprint gafoo |
#     #      awk -F: '$1 == "fpr" {print $10;}'"
#     # TODO: complete implementation
