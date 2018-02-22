import flask
import time

from coprs.views.status_ns import status_ns
from coprs.logic import builds_logic, coprs_logic
from coprs import helpers


def get_graph_data(start, end, step):
    chroots_dict = {}
    chroots = []
    chroot_names = {}
    tasks = builds_logic.BuildsLogic.get_tasks_by_time(start, end)
    steps = int(round((end - start) / step + 0.5))
    current_step = 0

    data = [[0] * (steps + 1), [1.0 * tasks.count() / steps] * (steps + 1), [0] * (steps + 1)]
    data[0][0] = 'tasks'
    data[1][0] = 'average'
    data[2][0] = 'time'

    for t in tasks:
        task = t.to_dict()
        while task['started_on'] > start + step * (current_step + 1):
            current_step += 1
        data[0][current_step + 1] += 1

        if task['mock_chroot_id'] not in chroots_dict:
            chroots_dict[task['mock_chroot_id']] = 1
        else:
            chroots_dict[task['mock_chroot_id']] += 1

    for i in range(0, steps):
        data[2][i + 1] = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start + (i * step)))

    for key in chroots_dict:
        chroots.append([key, chroots_dict[key]])

    mock_chroots = coprs_logic.MockChrootsLogic.get_multiple()
    for mock_chroot in mock_chroots:
        for l in chroots:
            if l[0] == mock_chroot.id:
                l[0] = mock_chroot.name

    return data, chroots


@status_ns.route("/")
@status_ns.route("/pending/")
def pending():
    tasks = builds_logic.BuildsLogic.get_pending_build_tasks(background=False).limit(300).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_pending_build_tasks(background=True).count()
    return flask.render_template("status/pending.html",
                                 number=len(tasks),
                                 tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/running/")
def running():
    tasks = builds_logic.BuildsLogic.get_build_tasks(helpers.StatusEnum("running")).limit(300).all()
    return flask.render_template("status/running.html",
                                 number=len(tasks),
                                 tasks=tasks)


@status_ns.route("/importing/")
def importing():
    tasks = builds_logic.BuildsLogic.get_build_importing_queue(background=False).limit(300).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_build_importing_queue(background=True).count()
    return flask.render_template("status/importing.html",
                                 number=len(list(tasks)),
                                 bg_tasks_cnt=bg_tasks_cnt,
                                 tasks=tasks)


@status_ns.route("/stats/")
def stats():
    current_time = int(time.time())
    data1, chroots1 = get_graph_data(current_time - 86400 + 1, current_time, 600) # last 24 hours
    data2, chroots2 = get_graph_data(current_time - 86400 * 90 + 1, current_time, 86400) # last 90 days
    return flask.render_template("status/stats.html",
                                 data1=data1,
                                 data2=data2,
                                 chroots1=chroots1,
                                 chroots2=chroots2)
