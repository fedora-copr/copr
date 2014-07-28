import flask, os

from urlparse import urlparse
from coprs.views.status_ns import status_ns
from coprs.logic import builds_logic
from coprs import helpers

@status_ns.route("/")
@status_ns.route("/waiting/")
def waiting():
    tasks = builds_logic.BuildsLogic.get_build_task_queue()
    return flask.render_template("status/waiting.html",
                                number=len(list(tasks)),
                                tasks=tasks)

@status_ns.route("/running/")
def running():
    tasks = builds_logic.BuildsLogic.get_build_tasks(helpers.StatusEnum("running"))
    return flask.render_template("status/running.html",
                                number=len(list(tasks)),
                                tasks=tasks)
