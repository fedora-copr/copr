# coding: utf-8

import flask

from coprs.views.misc import page_not_found, access_restricted
from coprs.exceptions import ObjectNotFound, AccessRestricted

coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")


@coprs_ns.app_errorhandler(ObjectNotFound)
def handle_404(error):
    return page_not_found(error.message)


@coprs_ns.app_errorhandler(AccessRestricted)
def handle_403(error):
    return access_restricted(error.message)
