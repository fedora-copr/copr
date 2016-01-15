import flask

from . import recent_ns
from coprs.logic import builds_logic
from coprs.views.misc import login_required

import logging

log = logging.getLogger(__name__)


@recent_ns.route("/")
@recent_ns.route("/all/")
def all():
    # tasks = bilds_logic.BuildsLogic.get_build_tasks(
    builds = builds_logic.BuildsLogic.get_recent_tasks(limit=20)
    # if flask.g:
    #    log.info("flask.g")\
    if flask.g.user is not None:
        user_builds = builds_logic.BuildsLogic.get_recent_tasks(user=flask.g.user, limit=20)
    else:
        user_builds = []

    return flask.render_template("recent/all.html",
                                 number=len(list(builds)),
                                 builds=builds,
                                 user_builds=user_builds)

@recent_ns.route("/my/")
@login_required
def my():
    # tasks = bilds_logic.BuildsLogic.get_build_tasks(
    builds = builds_logic.BuildsLogic.get_recent_tasks(limit=20)
    # if flask.g:
    #    log.info("flask.g")\
    if flask.g.user is not None:
        user_builds = builds_logic.BuildsLogic.get_recent_tasks(user=flask.g.user, limit=20)
    else:
        user_builds = []

    return flask.render_template("recent/my.html",
                                 number=len(list(builds)),
                                 builds=builds,
                                 user_builds=user_builds)
