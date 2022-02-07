# coding: utf-8

import flask
from coprs import app
from coprs import db
from coprs.exceptions import CoprHttpException
from coprs.views.misc import backend_authenticated
from . import stats_rcv_ns
from ...logic.stat_logic import CounterStatLogic, handle_be_stat_message


@stats_rcv_ns.route("/")
def ping():
    return "OK", 200


@stats_rcv_ns.route("/<counter_type>/<name>/", methods=['POST'])
@backend_authenticated
def increment(counter_type, name):
    app.logger.debug(flask.request.remote_addr)

    CounterStatLogic.incr(name, counter_type)
    db.session.commit()
    return "", 201


@stats_rcv_ns.route("/from_backend", methods=['POST'])
@backend_authenticated
def backend_stat_message_handler():
    try:
        handle_be_stat_message(flask.request.json)
        db.session.commit()
    except Exception as err:
        app.logger.exception(err)
        raise CoprHttpException from err

    return "OK", 201
