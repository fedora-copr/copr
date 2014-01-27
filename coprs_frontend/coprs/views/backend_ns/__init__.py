import flask

backend_ns = flask.Blueprint("backend_ns", __name__, url_prefix="/backend")
