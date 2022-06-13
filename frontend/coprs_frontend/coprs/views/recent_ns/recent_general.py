import flask

from . import recent_ns
from coprs.logic import builds_logic
from coprs.views.misc import login_required


@recent_ns.route("/")
@recent_ns.route("/all/")
def all():
    period_days = 2
    builds = builds_logic.BuildsLogic.get_recent_tasks(period_days=period_days)
    return flask.render_template("recent/all.html",
                                 number=len(list(builds)),
                                 builds=builds,
                                 period_days=period_days)

@recent_ns.route("/my/")
@login_required
def my():
    period_days = 30
    builds = builds_logic.BuildsLogic.get_recent_tasks(user=flask.g.user,
                                                       period_days=period_days)
    return flask.render_template("recent/my.html",
                                 number=len(list(builds)),
                                 builds=builds,
                                 period_days=period_days)
