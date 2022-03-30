import flask
from coprs.views.apiv3_ns import apiv3_ns
from coprs.views.misc import api_login_required


@apiv3_ns.route("/")
def home():
    return flask.jsonify({"version": 3})


def auth_check_response():
    """
    Used in misc and apiv3 for returning info about the user.
    """
    return flask.g.user.to_dict()


@apiv3_ns.route("/auth-check")
@api_login_required
def auth_check():
    return flask.jsonify(auth_check_response())
