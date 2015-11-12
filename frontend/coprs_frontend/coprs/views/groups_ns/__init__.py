# coding: utf-8

import flask

from coprs.views.misc import page_not_found, access_restricted
from coprs.exceptions import ObjectNotFound, AccessRestricted

groups_ns = flask.Blueprint("groups_ns", __name__, url_prefix="/groups")


@groups_ns.errorhandler(ObjectNotFound)
def handle_404(error):
    return page_not_found(error.message)


@groups_ns.errorhandler(AccessRestricted)
def handle_403(error):
    return access_restricted(error.message)
