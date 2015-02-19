# coding: utf-8
import flask

stats_rcv_ns = flask.Blueprint("stats_rcv_ns", __name__, url_prefix="/stats_rcv")
