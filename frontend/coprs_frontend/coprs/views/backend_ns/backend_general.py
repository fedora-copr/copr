import flask
import sqlalchemy

from copr_common.enums import StatusEnum
from coprs import db, app
from coprs import models
from coprs.logic import actions_logic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic, BuildConfigLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic
from coprs.exceptions import MalformedArgumentException, ObjectNotFound
from coprs.helpers import streamed_json

from coprs.views import misc
from coprs.views.backend_ns import backend_ns


@backend_ns.after_request
def send_frontend_version(response):
    """
    This sets the FE <=> BE API version.  We should bump this version anytime we
    do something new with the protocol.  On the Backend/builder side we can
    setup the version according to our needs.
    """
    response.headers['Copr-FE-BE-API-Version'] = '4'
    return response


@backend_ns.route("/importing/")
def dist_git_importing_queue():
    """
    Return list of builds that are waiting for dist-git to import the sources.
    """
    def _stream():
        builds_for_import = BuildsLogic.get_build_importing_queue()
        for build in builds_for_import:
            task = get_import_record(build)
            yield task
    return streamed_json(_stream())


@backend_ns.route("/get-import-task/<build_id>")
def get_import_task(build_id):
    """
    Return a single task that DistGit should import
    """
    build = BuildsLogic.get(build_id).one_or_none()
    task = get_import_record(build)
    return flask.jsonify(task)


def get_import_record(build):
    """
    Transform an ORM Build instance into a Python dictionary that is later
    converted to a JSON string and sent (as task build instructions) to Copr
    DistGit machine.
    """
    if not build:
        return None

    branches = set()
    for b_ch in build.build_chroots:
        branches.add(b_ch.mock_chroot.distgit_branch_name)

    return {
        "build_id": build.id,
        "owner": build.copr.owner_name,
        "project": build.copr_dirname,
        # TODO: we mix PR with normal builds here :-(
        "branches": list(branches),
        "pkg_name": build.package.name,
        "srpm_url": build.srpm_url,
        "sandbox": build.sandbox,
        "background": build.is_background,
    }


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


def get_build_record(task, for_backend=False):
    """
    Transform an ORM BuildChroot instance into a Python dictionary that is later
    converted to a JSON string and sent (as task build instructions) to Copr
    Backend or Copr Builder machine.

    The Backend needs only a limited amount of information to correctly schedule
    the task processing (what to build, when, how, where...), whilst Builder
    needs the full information to properly perform the build.

    The build queue may be rather large (tens of thousands tasks) in some peak
    situations, so we try to really limit the amount of data processed and sent
    to Backend (array).  OTOH, Builder's single-row queries are rather cheap and
    thus we don't have to pay attention to such optimizations.

    :param for_backend: True if the data are consumed by Backend (smaller
        dictionary output), False if the data are consumed by Builder (full task
        info).
    """
    if not task:
        return None

    build_record = None
    try:
        build_record = {
            "task_id": task.task_id,
            "build_id": task.build.id,
            "project_owner": task.build.copr.owner_name,
            "sandbox": task.build.sandbox,
            "background": bool(task.build.is_background),
            "chroot": task.mock_chroot.name,
            "tags": task.mock_chroot.tags,
        }

        if for_backend:
            return build_record

        build_record.update({
            "project_name": task.build.copr_name,
            "project_dirname": task.build.copr_dirname,
            "submitter": task.build.submitter[0],
            "repos": task.build.repos,
            "memory_reqs": task.build.memory_reqs,
            "timeout": task.build.timeout,
            "enable_net": task.build.enable_net,
            "git_repo": task.distgit_clone_url,
            "git_hash": task.git_hash,
            "package_name": task.build.package.name,
            "package_version": task.build.pkg_version,
            "uses_devel_repo": task.build.copr.devel_mode,
            "isolation": task.build.isolation,
            "fedora_review": task.build.copr.fedora_review,
            "appstream": bool(task.build.appstream),
        })

        copr_chroot = CoprChrootsLogic.get_by_name_safe(task.build.copr, task.mock_chroot.name)
        modules = copr_chroot.module_setup_commands
        if modules:
            build_record["modules"] = {'toggle': modules}

        build_config = BuildConfigLogic.generate_build_config(task.build.copr, task.mock_chroot.name)
        build_record["repos"] = build_config.get("repos")
        build_record["buildroot_pkgs"] = build_config.get("additional_packages")
        build_record["with_opts"] = build_config.get("with_opts")
        build_record["without_opts"] = build_config.get("without_opts")

        bch_bootstrap = BuildConfigLogic.build_bootstrap_setup(
            build_config, task.build)
        build_record.update(bch_bootstrap)
        bch_isolation = BuildConfigLogic.get_build_isolation(
            build_config, task.build)
        build_record.update(bch_isolation)

    except Exception as err:
        app.logger.exception(err)
        return None

    return build_record


def get_srpm_build_record(task, for_backend=False):
    """
    Transform an ORM Build instance (how to build SRPM) into a Python dictionary
    that is later converted to a JSON string and sent (as task build
    instructions) to Copr Backend or Copr Builder machine.  For more info see
    get_build_record() documentation.
    """
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
            "sandbox": task.sandbox,
            "background": bool(task.is_background),
            "chroot": chroot,
        }

        if for_backend:
            return build_record

        repos = (task.source_json_dict.get("repos", "") or "").split()
        build_record.update({
            "source_type": task.source_type,
            "source_json": task.source_json,
            "submitter": task.submitter[0],
            "project_name": task.copr_name,
            "project_dirname": task.copr_dirname,
            "appstream": bool(task.copr.appstream),
            "repos": BuildConfigLogic.get_additional_repo_views(repos, chroot),
        })

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


@backend_ns.route("/build-tasks/cancel-requests/")
def pending_cancel_builds():
    """
    Return the list of task IDs to be canceled.
    """
    task_ids = [x.what for x in models.CancelRequest.query.all()]
    return flask.jsonify(task_ids)


@backend_ns.route("/build-tasks/canceled/<task_id>/", methods=["POST", "PUT"])
@misc.backend_authenticated
def build_task_canceled(task_id):
    """ Report back to frontend that the task was canceled on backend """
    models.CancelRequest.query.filter_by(what=task_id).delete()
    was_running = flask.request.json
    if not was_running:
        if '-' in task_id:
            build_chroot = BuildsLogic.get_build_task(task_id)
            if build_chroot:
                build_chroot.status = StatusEnum("canceled")
        else:
            build = models.Build.query.filter_by(id=task_id).first()
            if build:
                build.source_status = StatusEnum("canceled")
    db.session.commit()
    return flask.jsonify("success")


@backend_ns.route("/pending-actions/")
def pending_actions():
    'get the list of actions backand should take care of'
    data = []
    for action in actions_logic.ActionsLogic.get_waiting():
        data.append({
            'id': action.id,
            'priority': action.priority or action.default_priority,
        })
    return flask.json.dumps(data)



@backend_ns.route("/action/<int:action_id>/")
def get_action(action_id):
    action = actions_logic.ActionsLogic.get(action_id).one()
    action_record = action.to_dict()
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

    # This code is really expensive, and takes a long time when there is a large
    # build queue.  We want to avoid repeated reload of models.Batch data, and
    # for that we need to have it strongly referenced.
    cache = set()

    def build_ready(build):
        """ Is the build blocked? """
        cache.add(build.batch)
        return not build.blocked

    def _stream():
        args = {"data_type": "for_backend"}

        app.logger.info("Generating SRPM builds")
        for build in BuildsLogic.get_pending_srpm_build_tasks(**args):
            if not build_ready(build):
                continue
            record = get_srpm_build_record(build, for_backend=True)
            yield record

        app.logger.info("Generating RPM builds")
        for build_chroot in BuildsLogic.get_pending_build_tasks(**args):
            if not build_ready(build_chroot.build):
                continue
            record = get_build_record(build_chroot, for_backend=True)
            yield record

    return streamed_json(_stream())


@backend_ns.route("/get-build-task/<task_id>/")
@backend_ns.route("/get-build-task/<task_id>")
def get_build_task(task_id):
    try:
        task = BuildsLogic.get_build_task(task_id)
    except MalformedArgumentException:
        jsonout = flask.jsonify({'msg': 'Invalid task ID'})
        jsonout.status_code = 500
        return jsonout
    except sqlalchemy.orm.exc.NoResultFound:
        jsonout = flask.jsonify({'msg': 'Specified task ID not found'})
        jsonout.status_code = 404
        return jsonout
    build_record = get_build_record(task)
    return flask.jsonify(build_record)


@backend_ns.route("/get-srpm-build-task/<build_id>/")
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
            app.logger.info("rescheduling source build %s", build.id)
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
            app.logger.info("rescheduling build {} chroot: {}"
                            .format(build.id, build_chroot.name))
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

@backend_ns.route("/chroots-prunerepo-status/")
def chroots_prunerepo_status():
    return flask.jsonify(MockChrootsLogic.chroots_prunerepo_status())

@backend_ns.route("/final-prunerepo-done/", methods=["POST", "PUT"])
@misc.backend_authenticated
def final_prunerepo_done():
    chroots_pruned = flask.request.get_json()
    return flask.jsonify(MockChrootsLogic.prunerepo_finished(chroots_pruned))
