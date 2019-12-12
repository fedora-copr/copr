import flask
from time import time

from copr_common.enums import StatusEnum
from coprs.views.status_ns import status_ns
from coprs.logic import builds_logic
from coprs.logic import complex_logic


@status_ns.context_processor
def inject_common_blueprint_variables():
    return dict(queue_sizes=complex_logic.ComplexLogic.get_queue_sizes())


@status_ns.route("/")
@status_ns.route("/pending/")
def pending():
    tasks = builds_logic.BuildsLogic.get_pending_build_tasks(background=False).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_pending_build_tasks(background=True).count()
    return render_status("pending", tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/running/")
def running():
    tasks = builds_logic.BuildsLogic.get_build_tasks(StatusEnum("running")).all()
    return render_status("running", tasks=tasks)


@status_ns.route("/importing/")
def importing():
    tasks = builds_logic.BuildsLogic.get_build_importing_queue(background=False).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_build_importing_queue(background=True).count()
    return render_status("importing", tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


def render_status(build_status, tasks, bg_tasks_cnt=None):
    return flask.render_template("status/{}.html".format(build_status), number=len(tasks),
                                 tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/stats/")
def stats():
    curr_time = int(time())
    chroots_24h = builds_logic.BuildsLogic.get_chroot_histogram(curr_time - 86400, curr_time)
    chroots_90d = builds_logic.BuildsLogic.get_chroot_histogram(curr_time - 90*86400, curr_time)
    data_24h = builds_logic.BuildsLogic.get_task_graph_data('10min')
    data_90d = builds_logic.BuildsLogic.get_task_graph_data('24h')
    actions_24h = builds_logic.ActionsLogic.get_action_graph_data('10min')
    actions_90d = builds_logic.ActionsLogic.get_action_graph_data('24h')

    return flask.render_template("status/stats.html",
                                 data1=data_24h,
                                 data2=data_90d,
                                 chroots1=chroots_24h,
                                 chroots2=chroots_90d,
                                 actions1=actions_24h,
                                 actions2=actions_90d
                                 )
