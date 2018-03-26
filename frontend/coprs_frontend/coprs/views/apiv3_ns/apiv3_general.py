import flask
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic


@apiv3_ns.route("/")
def home():
    return flask.jsonify({"version": 3})
