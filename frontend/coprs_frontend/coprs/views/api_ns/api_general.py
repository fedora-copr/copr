"""
General API views that doesn't change with new major versions.
Views that return JSON probably doesn't belong here, only views that render HTML
and that are supposed to be displayed in a web browser.
"""

import flask
from coprs import db
from coprs.views.api_ns import api_ns
from coprs.views.misc import login_required
from coprs.logic.api_logic import APILogic


@api_ns.route("/")
def api_home():
    """
    Render the home page of the api.
    This page provides information on how to call/use the API.
    """

    return flask.render_template("api.html")


@api_ns.route("/new/", methods=["GET", "POST"])
@login_required
def api_new_token():
    """
    Generate a new API token for the current user.
    """
    APILogic.generate_api_token(flask.g.user)
    db.session.commit()
    return flask.redirect(flask.url_for("api_ns.api_home"))
