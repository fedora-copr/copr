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
    rpm_tasks = builds_logic.BuildsLogic.get_pending_build_tasks(background=False).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_pending_build_tasks(background=True).count()
    tasks = list(zip(["rpm"] * len(rpm_tasks),
                     [x.build.submitted_on for x in rpm_tasks],
                     rpm_tasks))
    srpm_tasks = builds_logic.BuildsLogic.get_pending_srpm_build_tasks(background=False).all()
    bg_tasks_cnt += builds_logic.BuildsLogic.get_pending_srpm_build_tasks(background=True).count()
    srpm_tasks = list(zip(["srpm"] * len(srpm_tasks),
                          [x.submitted_on for x in srpm_tasks],
                          srpm_tasks))
    tasks.extend(srpm_tasks)
    return render_status("pending", tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/running/")
def running():
    rpm_tasks = builds_logic.BuildsLogic.get_build_tasks(StatusEnum("running")).all()
    tasks = list(zip(["rpm"] * len(rpm_tasks),
                     [x.started_on for x in rpm_tasks],
                     rpm_tasks))
    srpm_tasks = builds_logic.BuildsLogic.get_srpm_build_tasks(StatusEnum("running")).all()
    srpm_tasks = list(zip(["srpm"] * len(srpm_tasks),
                          [x.submitted_on for x in srpm_tasks],
                          srpm_tasks))
    tasks.extend(srpm_tasks)
    return render_status("running", tasks=tasks)


@status_ns.route("/importing/")
def importing():
    tasks = builds_logic.BuildsLogic.get_build_importing_queue(background=False).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_build_importing_queue(background=True).count()
    tasks = list(zip(["rpm"] * len(tasks),
                     [x.submitted_on for x in tasks],
                     tasks))
    return render_status("importing", tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/starting/")
def starting():
    tasks = builds_logic.BuildsLogic.get_build_tasks(StatusEnum("starting")).all()
    tasks = list(zip(["rpm"] * len(tasks),
                     [x.build.submitted_on for x in tasks],
                     tasks))
    srpm_tasks = builds_logic.BuildsLogic.get_srpm_build_tasks(StatusEnum("starting")).all()
    srpm_tasks = list(zip(["srpm"] * len(srpm_tasks),
                          [x.submitted_on for x in srpm_tasks],
                          srpm_tasks))
    tasks.extend(srpm_tasks)
    return render_status("starting", tasks=tasks)


def render_status(build_status, tasks, bg_tasks_cnt=None):
    return flask.render_template("status.html", number=len(tasks),
                                 tasks=tasks, bg_tasks_cnt=bg_tasks_cnt,
                                 state_of_tasks=build_status)


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
