import flask

webhooks_ns = flask.Blueprint("webhooks_ns", __name__, url_prefix="/webhooks")
