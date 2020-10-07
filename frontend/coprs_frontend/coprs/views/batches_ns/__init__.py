"""
Plug-in the /batches/ namespace
"""

import flask

batches_ns = flask.Blueprint("batches_ns", __name__, url_prefix="/batches")
