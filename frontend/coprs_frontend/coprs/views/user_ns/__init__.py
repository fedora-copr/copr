import flask


user_ns = flask.Blueprint("user_ns", __name__, url_prefix="/user")
