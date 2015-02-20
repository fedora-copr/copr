# coding: utf-8

import flask
from coprs import app
from coprs import db
from coprs.helpers import REPO_DL_STAT_FMT, CounterStatType
from ..misc import intranet_required
from . import stats_rcv_ns
from ...logic.stat_logic import CounterStatLogic

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
@intranet_required  # ?
def logstash_handler():
    # import ipdb; ipdb.set_trace()
    json = flask.request.json
    if "request" in json:
        #             0 1     2   3    4    5
        # "request": "/coprs/bob/foox/repo/epel-5/bob-foox-epel-5.repo",
        req_split = json["request"].split("/")
        kwargs = dict(
            user=req_split[2],
            copr=req_split[3],
            name_release=req_split[5]
        )
        name = REPO_DL_STAT_FMT.format(**kwargs)
        app.logger.debug("kwargs: {}; name: {}".format(kwargs, name))

        CounterStatLogic.incr(name=name,
                              counter_type=CounterStatType.REPO_DL)
        db.session.commit()

    return "", 201
