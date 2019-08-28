import flask
import sqlalchemy

from copr_common.enums import StatusEnum
from coprs import db, app
from coprs import helpers
from coprs import models
from coprs import exceptions
from coprs.logic import actions_logic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.coprs_logic import MockChrootsLogic
from coprs.exceptions import MalformedArgumentException

from coprs.views import misc
from coprs.views.backend_ns import backend_ns
from sqlalchemy.sql import false, true

import json
import logging

log = logging.getLogger(__name__)


@backend_ns.route("/importing/")
def dist_git_importing_queue():
    """
    Return list of builds that are waiting for dist-git to import the sources.
    """
    tasks = []

    builds_for_import = BuildsLogic.get_build_importing_queue().filter(models.Build.is_background == false()).limit(100).all()
    if not builds_for_import:
        builds_for_import = BuildsLogic.get_build_importing_queue().filter(models.Build.is_background == true()).limit(30).all()

    for build in builds_for_import:
        branches = set()
        for b_ch in build.build_chroots:
            branches.add(b_ch.mock_chroot.distgit_branch_name)

        tasks.append({
            "build_id": build.id,
            "owner": build.copr.owner_name,
            "project": build.copr_dirname,
            # TODO: we mix PR with normal builds here :-(
            "branches": list(branches),
            "pkg_name": build.package.name,
            "srpm_url": build.srpm_url,
        })

    return flask.jsonify(tasks)


@backend_ns.route("/import-completed/", methods=["POST", "PUT"])
@misc.backend_authenticated
def dist_git_upload_completed():
    app.logger.debug(flask.request.json)
    build_id = flask.request.json.get("build_id")

    try:
        build = ComplexLogic.get_build_safe(build_id)
    except ObjectNotFound:
        return flask.jsonify({"updated": False})

    collected_branch_chroots = []
    for branch, git_hash in flask.request.json.get("branch_commits", {}).items():
        branch_chroots = BuildsLogic.get_buildchroots_by_build_id_and_branch(build_id, branch)
        for ch in branch_chroots:
            ch.status = StatusEnum("pending")
            ch.git_hash = git_hash
            db.session.add(ch)
            collected_branch_chroots.append((ch.task_id))

    final_source_status = StatusEnum("succeeded")
    for ch in build.build_chroots:
        if ch.task_id not in collected_branch_chroots:
            final_source_status = StatusEnum("failed")
            ch.status = StatusEnum("failed")
            db.session.add(ch)

    build.source_status = final_source_status
    db.session.add(build)
    db.session.commit()

    BuildsLogic.delete_local_source(build)
    return flask.jsonify({"updated": True})


def get_build_record(task):
    if not task:
        return None

    build_record = None
    try:
        build_record = {
            "task_id": task.task_id,
            "build_id": task.build.id,
            "project_owner": task.build.copr.owner_name,
            "project_name": task.build.copr_name,
            "project_dirname": task.build.copr_dirname,
            "submitter": task.build.submitter[0],
            "sandbox": task.build.sandbox,
            "chroot": task.mock_chroot.name,
            "repos": task.build.repos,
            "memory_reqs": task.build.memory_reqs,
            "timeout": task.build.timeout,
            "enable_net": task.build.enable_net,
            "git_repo": task.build.package.dist_git_repo,
            "git_hash": task.git_hash,
            "source_type": helpers.BuildSourceEnum("scm"),
            "source_json": json.dumps(
                {'clone_url': task.build.package.dist_git_clone_url, 'committish': task.git_hash}),
            "fetch_sources_only": True,
            "package_name": task.build.package.name,
            "package_version": task.build.pkg_version,
        }

    except Exception as err:
        app.logger.exception(err)
        return None

    return build_record


def get_srpm_build_record(task):
    if not task:
        return None

    if task.source_type_text == "custom":
        chroot = task.source_json_dict['chroot']
    else:
        chroot = None

    try:
        build_record = {
            "task_id": task.task_id,
            "build_id": task.id,
            "project_owner": task.copr.owner_name,
            "project_name": task.copr_name,
            "project_dirname": task.copr_dirname,
            "submitter": task.submitter[0],
            "sandbox": task.sandbox,
            "source_type": task.source_type,
            "source_json": task.source_json,
            "chroot": chroot,
        }

    except Exception as err:
        app.logger.exception(err)
        return None

    return build_record


@backend_ns.route("/pending-action/")
def pending_action():
    """
    Return a single action.
    """
    action_record = None
    action = actions_logic.ActionsLogic.get_waiting().first()
    if action:
        action_record = action.to_dict(options={
            "__columns_except__": ["result", "message", "ended_on"]
        })
    return flask.jsonify(action_record)


@backend_ns.route("/pending-action-count/")
def pending_action_count():
    """
    Return pending action count.
    """
    return flask.jsonify(actions_logic.ActionsLogic.get_waiting().count())


@backend_ns.route("/pending-jobs/")
def pending_jobs():
    """
    Return the job queue.
    """
    srpm_tasks = [build for build in BuildsLogic.get_pending_srpm_build_tasks() if not build.blocked]
    build_records = (
        [get_srpm_build_record(task) for task in srpm_tasks] +
        [get_build_record(task) for task in BuildsLogic.get_pending_build_tasks()]
    )
    log.info('Selected build records: {}'.format(build_records))
    return flask.jsonify(build_records)


@backend_ns.route("/get-build-task/<task_id>")
def get_build_task(task_id):
    try:
        task = BuildsLogic.get_build_task(task_id)
    except exceptions.MalformedArgumentException:
        jsonout = flask.jsonify({'msg': 'Invalid task ID'})
        jsonout.status_code = 500
        return jsonout
    except sqlalchemy.orm.exc.NoResultFound:
        jsonout = flask.jsonify({'msg': 'Specified task ID not found'})
        jsonout.status_code = 404
        return jsonout
    build_record = get_build_record(task)
    return flask.jsonify(build_record)


@backend_ns.route("/get-srpm-build-task/<build_id>")
def get_srpm_build_task(build_id):
    try:
        task = BuildsLogic.get_srpm_build_task(build_id)
    except sqlalchemy.orm.exc.NoResultFound:
        jsonout = flask.jsonify({'msg': 'Specified task ID not found'})
        jsonout.status_code = 404
        return jsonout
    build_record = get_srpm_build_record(task)
    return flask.jsonify(build_record)


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

        db.session.commit()
        result.update({"updated_{0}_ids".format(typ): list(existing.keys()),
                       "non_existing_{0}_ids".format(typ): non_existing_ids})

    return flask.jsonify(result)


@backend_ns.route("/starting_build/", methods=["POST", "PUT"])
@misc.backend_authenticated
def starting_build():
    """
    Check if the build is not cancelled and set it to starting state
    """
    data = flask.request.json

    try:
        build = ComplexLogic.get_build_safe(data.get('build_id'))
    except ObjectNotFound:
        return flask.jsonify({"can_start": False})

    if build.canceled:
        return flask.jsonify({"can_start": False})

    BuildsLogic.update_state_from_dict(build, data)
    db.session.commit()
    return flask.jsonify({"can_start": True})


@backend_ns.route("/reschedule_all_running/", methods=["POST", "PUT"])
@misc.backend_authenticated
def reschedule_all_running():
    to_reschedule = \
        BuildsLogic.get_build_tasks(StatusEnum("starting")).all() + \
        BuildsLogic.get_build_tasks(StatusEnum("running")).all()

    for build_chroot in to_reschedule:
        build_chroot.status = StatusEnum("pending")
        db.session.add(build_chroot)

    to_reschedule = \
        BuildsLogic.get_srpm_build_tasks(StatusEnum("starting")).all() + \
        BuildsLogic.get_srpm_build_tasks(StatusEnum("running")).all()

    for build in to_reschedule:
        build.source_status = StatusEnum("pending")
        db.session.add(build)

    db.session.commit()

    return "OK", 200


@backend_ns.route("/reschedule_build_chroot/", methods=["POST", "PUT"])
@misc.backend_authenticated
def reschedule_build_chroot():
    response = {}
    build_id = flask.request.json.get("build_id")
    task_id = flask.request.json.get("task_id")
    chroot = flask.request.json.get("chroot")

    try:
        build = ComplexLogic.get_build_safe(build_id)
    except ObjectNotFound:
        response["result"] = "noop"
        response["msg"] = "Build {} wasn't found".format(build_id)
        return flask.jsonify(response)

    if build.canceled:
        response["result"] = "noop"
        response["msg"] = "build was cancelled, ignoring"
        return flask.jsonify(response)

    run_statuses = set([StatusEnum("starting"), StatusEnum("running")])

    if task_id == build.task_id:
        if build.source_status in run_statuses:
            log.info("rescheduling srpm build {}".format(build.id))
            BuildsLogic.update_state_from_dict(build, {
                "task_id": task_id,
                "status": StatusEnum("pending")
            })
            db.session.commit()
            response["result"] = "done"
        else:
            response["result"] = "noop"
            response["msg"] = "build is not in running states, ignoring"
    else:
        build_chroot = build.chroots_dict_by_name.get(chroot)
        if build_chroot and build_chroot.status in run_statuses:
            log.info("rescheduling build {} chroot: {}".format(build.id, build_chroot.name))
            BuildsLogic.update_state_from_dict(build, {
                "task_id": task_id,
                "chroot": chroot,
                "status": StatusEnum("pending")
            })
            db.session.commit()
            response["result"] = "done"
        else:
            response["result"] = "noop"
            response["msg"] = "build chroot is not in running states, ignoring"

    return flask.jsonify(response)

@backend_ns.route("/chroots-prunerepo-status/", methods=["POST", "PUT"])
def chroots_prunerepo_status():
    return flask.jsonify(MockChrootsLogic.chroots_prunerepo_status())

@backend_ns.route("/final-prunerepo-done/", methods=["POST", "PUT"])
@misc.backend_authenticated
def final_prunerepo_done():
    chroots_pruned = flask.request.get_json()
    return flask.jsonify(MockChrootsLogic.prunerepo_finished(chroots_pruned))