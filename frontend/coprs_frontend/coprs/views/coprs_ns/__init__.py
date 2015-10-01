# coding: utf-8

import flask

from coprs.views.misc import page_not_found
from coprs.exceptions import ObjectNotFound

coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")


@coprs_ns.app_errorhandler(ObjectNotFound)
def handle_404(error):
    return page_not_found(error.message)
