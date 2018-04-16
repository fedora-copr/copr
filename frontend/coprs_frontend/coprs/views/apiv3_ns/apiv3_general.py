import flask
from coprs.views.apiv3_ns import apiv3_ns
from coprs.views.misc import api_login_required


@apiv3_ns.route("/")
def home():
    return flask.jsonify({"version": 3})


@apiv3_ns.route("/auth-check")
@api_login_required
def auth_check():
    return flask.jsonify(flask.g.user.to_dict())
