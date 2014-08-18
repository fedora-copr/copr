import flask

recent_ns = flask.Blueprint("recent_ns", __name__, url_prefix="/recent")
