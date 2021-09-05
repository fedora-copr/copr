"""
General API views that doesn't change with new major versions.
Views that return JSON probably doesn't belong here, only views that render HTML
and that are supposed to be displayed in a web browser.
"""

import base64
import datetime
import flask
from coprs import db
from coprs import helpers
from coprs.views.api_ns import api_ns
from coprs.views.misc import login_required


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

    user = flask.g.user
    copr64 = base64.b64encode(b"copr") + b"##"
    api_login = helpers.generate_api_token(
        flask.current_app.config["API_TOKEN_LENGTH"] - len(copr64))
    user.api_login = api_login
    user.api_token = helpers.generate_api_token(
        flask.current_app.config["API_TOKEN_LENGTH"])
    user.api_token_expiration = datetime.date.today() + \
        datetime.timedelta(
            days=flask.current_app.config["API_TOKEN_EXPIRATION"])

    db.session.add(user)
    db.session.commit()
    return flask.redirect(flask.url_for("api_ns.api_home"))
