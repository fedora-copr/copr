# coding: utf-8

import flask
from coprs import rcp
from coprs import app
from coprs import db
from coprs.helpers import REPO_DL_STAT_FMT, CounterStatType
from ..misc import intranet_required
from . import stats_rcv_ns
from ...logic.stat_logic import CounterStatLogic, handle_logstash


@stats_rcv_ns.route("/")
def ping():
    return "OK", 200


@stats_rcv_ns.route("/<counter_type>/<name>/", methods=['POST'])
@intranet_required
def increment(counter_type, name):
    app.logger.debug(flask.request.remote_addr)

    CounterStatLogic.incr(name, counter_type)
    db.session.commit()
    return "", 201


@stats_rcv_ns.route("/from_logstash", methods=['POST'])
@intranet_required
def logstash_handler():
    try:
        handle_logstash(rcp.get_connection(), flask.request.json)
    except Exception as err:
        app.logger.exception(err)

    return "", 201
