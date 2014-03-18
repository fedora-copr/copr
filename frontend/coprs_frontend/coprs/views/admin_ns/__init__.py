import flask

admin_ns = flask.Blueprint("admin_ns", __name__, url_prefix="/admin")
