import flask

status_ns = flask.Blueprint("status_ns", __name__, url_prefix="/status")
