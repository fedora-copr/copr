import flask
import sys
import time
import os

from coprs import db
from coprs import helpers
from coprs.helpers import StatusEnum
from coprs.logic import actions_logic
from coprs.logic.builds_logic import BuildsLogic

from coprs.views import misc
from coprs.views.backend_ns import backend_ns
from whoosh.index import LockError

import logging
log = logging.getLogger(__name__)



@backend_ns.route("/uploading/")
#@misc.backend_authenticated
def dist_git_uploading_queue():
    """
    Return list of builds that are waiting for dist git to import the sources.
    """
    builds_list = [
        {
            "task_id": "{}-{}".format(task.build.id, task.mock_chroot.name),
            "project_owner": task.build.copr.owner.name,
            "project_name": task.build.copr.name,
            "package_name": helpers.parse_package_name(os.path.basename(task.build.pkgs)),
            "pkgs": task.build.pkgs,
            "chroot": task.mock_chroot.name,
        }
        for task in BuildsLogic.get_build_task_queue().limit(200)
    ]

    response_dict = {"builds": builds_list}

    return flask.jsonify(response_dict)

@backend_ns.route("/waiting/")
@misc.backend_authenticated
def waiting():
    """
    Return list of waiting actions and builds.
    """

    # models.Actions
    actions_list = [
        action.to_dict(options={
            "__columns_except__": ["result", "message", "ended_on"]
        })
        for action in actions_logic.ActionsLogic.get_waiting()
    ]

    # tasks represented by models.BuildChroot with some other stuff
    builds_list = [
        {
            "task_id": "{}-{}".format(task.build.id, task.mock_chroot.name),
            "build_id": task.build.id,
            "project_owner": task.build.copr.owner.name,
            "project_name": task.build.copr.name,
            "submitter": task.build.user.name,
            "pkgs": task.build.pkgs,
            "chroot": task.mock_chroot.name,
            "buildroot_pkgs": task.build.copr.buildroot_pkgs(task.mock_chroot),
            "repos": task.build.repos,
            "memory_reqs": task.build.memory_reqs,
            "timeout": task.build.timeout,
            "enable_net": task.build.enable_net,
        }
        for task in BuildsLogic.get_build_task_queue().limit(200)
    ]
    response_dict = {"actions": actions_list, "builds": builds_list}
    return flask.jsonify(response_dict)


@backend_ns.route("/update/", methods=["POST", "PUT"])
@misc.backend_authenticated
def update():
    result = {}

    request_data = flask.request.json
    for typ, logic_cls in [("actions", actions_logic.ActionsLogic),
                           ("builds", BuildsLogic)]:

        if typ not in request_data:
            continue

        to_update = {}
        for obj in request_data[typ]:
            to_update[obj["id"]] = obj

        existing = {}
        for obj in logic_cls.get_by_ids(to_update.keys()).all():
            existing[obj.id] = obj

        non_existing_ids = list(set(to_update.keys()) - set(existing.keys()))

        for i, obj in existing.items():
            logic_cls.update_state_from_dict(obj, to_update[i])

        i = 5
        exc_info = None
        while i > 0:
            try:
                db.session.commit()
                i = -100
            except LockError:
                i -= 1
                exc_info = sys.exc_info()[2]
                time.sleep(5)

        if i != -100:
            raise LockError(None).with_traceback(exc_info)

        result.update({"updated_{0}_ids".format(typ): list(existing.keys()),
                       "non_existing_{0}_ids".format(typ): non_existing_ids})

    return flask.jsonify(result)


@backend_ns.route("/starting_build/", methods=["POST", "PUT"])
@misc.backend_authenticated
def starting_build():
    """
    Check if the build is not cancelled and set it to running state
    """

    result = {"can_start": False}

    if "build_id" in flask.request.json and "chroot" in flask.request.json:
        build = BuildsLogic.get_by_id(flask.request.json["build_id"])
        chroot = flask.request.json.get("chroot")
        if build and chroot and not build.canceled:
            log.info("mark build {} chroot {} as starting".format(build.id, chroot))
            BuildsLogic.update_state_from_dict(build, {
                "chroot": chroot,
                "status": StatusEnum("starting")
            })
            db.session.commit()
            result["can_start"] = True

    return flask.jsonify(result)


@backend_ns.route("/reschedule_all_running/", methods=["POST"])
@misc.backend_authenticated
def reschedule_all_running():
    """
    Add-hoc handle. Remove after implementation of persistent task handling in copr-backend
    """
    to_reschedule = \
        BuildsLogic.get_build_tasks(StatusEnum("starting")).all() + \
        BuildsLogic.get_build_tasks(StatusEnum("running")).all()

    if to_reschedule:
        for build_chroot in to_reschedule:
            build_chroot.status = StatusEnum("pending")
            db.session.add(build_chroot)

        db.session.commit()

    return "OK", 200


@backend_ns.route("/reschedule_build_chroot/", methods=["POST", "PUT"])
@misc.backend_authenticated
def reschedule_build_chroot():
    response = {}
    if "build_id" in flask.request.json and "chroot" in flask.request.json:
        build = BuildsLogic.get_by_id(flask.request.json["build_id"])
    else:
        response["result"] = "bad request"
        response["msg"] = "Request missing  `build_id` and/or `chroot`"
        return flask.jsonify(response)

    if build:
        if build.canceled:
            response["result"] = "noop"
            response["msg"] = "build was cancelled, ignoring"
        else:
            chroot = flask.request.json["chroot"]
            build_chroot = build.chroots_dict_by_name.get(chroot)
            run_statuses = set([StatusEnum("starting"), StatusEnum("running")])
            if build_chroot and build_chroot.status in run_statuses:
                log.info("rescheduling build {} chroot: {}".format(build.id, build_chroot.name))
                BuildsLogic.update_state_from_dict(build, {
                    "chroot": chroot,
                    "status": StatusEnum("pending")
                })
                db.session.commit()
                response["result"] = "done"
            else:
                response["result"] = "noop"
                response["msg"] = "build is not in running states, ignoring"

    else:
        response["result"] = "noop"
        response["msg"] = "Build {} wasn't found".format(flask.request.json["build_id"])

    return flask.jsonify(response)
