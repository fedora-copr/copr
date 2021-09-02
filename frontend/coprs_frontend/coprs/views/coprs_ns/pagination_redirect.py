"""
Several Copr WebUI pages require the server-side pagination, and the way the
pagination html tool works requires us to provide additional redirect routes for
the pages.
"""

import flask
from coprs.views.coprs_ns import coprs_ns
from coprs import helpers


@coprs_ns.route("/<username>/<coprname>/builds/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/builds/", methods=["POST"])
@coprs_ns.route("/<username>/<coprname>/packages/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/packages/", methods=["POST"])
@coprs_ns.route("/<username>/<coprname>/monitor/", methods=["POST"])
@coprs_ns.route("/<username>/<coprname>/monitor/<detailed>", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/monitor/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/monitor/<detailed>", methods=["POST"])
def copr_pagination_redirect(**_kwargs):
    """
    Redirect the current page to the very same page, with just the '?page=<N>'
    argument changed.
    """
    to_page = flask.request.form.get('go_to_page', 1)
    return flask.redirect(helpers.current_url(page=to_page))
