from collections import Counter, defaultdict
from time import time

import flask

from copr_common.enums import StatusEnum
from coprs.views.status_ns import status_ns
from coprs.logic import batches_logic
from coprs.logic import builds_logic
from coprs.logic import complex_logic
from coprs import cache

PENDING_ALL_CACHE_SECONDS = 2*60

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

@status_ns.route("/pending/all/")
@cache.memoize(timeout=PENDING_ALL_CACHE_SECONDS)
def pending_all():
    """
    Provide the overview for _all_ the pending jobs.
    """

    # Get "for_backend" type of data, which are much cheaper to get.  This page
    # is for admins, to analyze the build queue (to allow us to understand best
    # what backend sees).
    rpm_tasks = builds_logic.BuildsLogic.get_pending_build_tasks(data_type="overview")

    owner_stats = Counter()
    owner_substats = defaultdict(lambda: {
        "projects": Counter(),
        "chroots": Counter(),
        "background": Counter(),
    })

    project_stats = Counter()
    background_stats = Counter()
    chroot_stats = Counter()

    def _calc_task(owner_name, project_name, chroot_name, background):
        owner_stats[owner_name] += 1
        owner = owner_substats[owner_name]
        owner["projects"][project_name] += 1
        owner["chroots"][chroot_name] += 1
        owner["background"][background] += 1
        project_stats[project_name] += 1
        chroot_stats[chroot_name] += 1
        background_stats[background] += 1


    for task in rpm_tasks:
        _calc_task(
            task.build.copr.owner.name,
            task.build.copr.full_name,
            task.mock_chroot.name,
            task.build.is_background,
        )

    srpm_tasks = builds_logic.BuildsLogic.get_pending_srpm_build_tasks(data_type="overview").all()
    for task in srpm_tasks:
        _calc_task(
            task.copr.owner.name,
            task.copr.full_name,
            "srpm-builds",
            task.is_background,
        )

    calculated_stats = {
        "owners": owner_stats,
        "owners_details": owner_substats,
        "projects": project_stats,
        "chroots": chroot_stats,
        "background": background_stats,
    }

    return flask.render_template(
        "status_overview.html",
        stats=calculated_stats,
        state_of_tasks="pending",
        cache_seconds=PENDING_ALL_CACHE_SECONDS,
    )


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


@status_ns.route("/batches/")
def batches():
    """ Print the list (tree) of batches """
    trees = batches_logic.BatchesLogic.pending_batch_trees()
    return flask.render_template("status/batch_list.html", batch_trees=trees)


@status_ns.route("/batches/detail/<int:batch_id>/")
def coprs_batch_detail(batch_id):
    """ Print the list (tree) of batches """
    chain = batches_logic.BatchesLogic.batch_chain(batch_id)
    batch = chain[0]
    deps = chain[1:]
    return flask.render_template("batches/detail.html", batch=batch, deps=deps)


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
