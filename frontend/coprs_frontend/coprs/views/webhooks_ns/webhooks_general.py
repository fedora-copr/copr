import logging
import os
import tempfile
import time
import shutil
from typing import Optional

import flask
from functools import wraps

from coprs import db, app
from coprs import models

from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.coprs_logic import CoprsLogic, CoprDirsLogic

from coprs.exceptions import (
        AccessRestricted,
        BadRequest,
        ObjectNotFound,
)

from coprs.views.webhooks_ns import webhooks_ns


log = logging.getLogger(__name__)


def skip_invalid_calls(route):
    """
    A best effort attempt to drop hook callswhich should not obviously end up
    with new build request (thus allocated build-id).
    """
    @wraps(route)
    def decorated_function(*args, **kwargs):
        if 'X-GitHub-Event' in flask.request.headers:
            event = flask.request.headers["X-GitHub-Event"]
            if event == "ping":
                return "SKIPPED\n", 200
        return route(*args, **kwargs)

    return decorated_function


def copr_id_and_uuid_required(route):
    @wraps(route)
    def decorated_function(**kwargs):
        if not 'copr_id' in kwargs or not 'uuid' in kwargs:
            return 'COPR_ID_OR_UUID_TOKEN_MISSING\n', 400

        copr_id = kwargs.pop('copr_id')
        try:
            copr = ComplexLogic.get_copr_by_id(copr_id)
        except ObjectNotFound:
            return "PROJECT_NOT_FOUND\n", 404

        if copr.webhook_secret != kwargs.pop('uuid'):
            return "BAD_UUID\n", 403

        return route(copr, **kwargs)

    return decorated_function


def package_name_required(route):
    @wraps(route)
    def decorated_function(copr, **kwargs):
        if not 'package_name' in kwargs:
            return 'PACKAGE_NAME_REQUIRED\n', 400

        package_name = kwargs.pop('package_name')
        try:
            package = ComplexLogic.get_package(copr, package_name)
        except ObjectNotFound:
            return "PACKAGE_NOT_FOUND\n", 404

        return route(copr, package, **kwargs)

    return decorated_function


def add_webhook_history_record(webhook_uuid, user_agent=None,
                               builds_initiated_via_hook=None):
    """
    This method adds info of an intercepted webhook to webhook_history db
    and updates the Build table with the corresponding webhook_history ID.
    """
    if builds_initiated_via_hook is None:
        log.debug("No build initiated. Webhook not logged to db.")
        return

    webhook_record = models.WebhookHistory(created_on=int(time.time()),
                                          webhook_uuid=webhook_uuid,
                                          user_agent=user_agent)
    db.session.add(webhook_record)

    for build in builds_initiated_via_hook:
        build.webhook_history = webhook_record


@webhooks_ns.route("/bitbucket/<int:copr_id>/<uuid>/", methods=["POST"])
@webhooks_ns.route("/bitbucket/<int:copr_id>/<uuid>/<string:pkg_name>/", methods=["POST"])
def webhooks_bitbucket_push(copr_id, uuid, pkg_name: Optional[str] = None):
    # For the documentation of the data we receive see:
    # https://confluence.atlassian.com/bitbucket/event-payloads-740262817.html
    copr = ComplexLogic.get_copr_by_id(copr_id)
    if copr.webhook_secret != uuid:
        raise AccessRestricted("This webhook is not valid")

    try:
        webhook_uuid = flask.request.headers.get('X-Hook-UUID')
        user_agent = flask.request.headers.get('User-Agent')
        payload = flask.request.json
        api_url = payload['repository']['links']['self']['href']
        clone_url = payload['repository']['links']['html']['href']
        commits = []
        ref_type = payload['push']['changes'][0]['new']['type']
        ref = payload['push']['changes'][0]['new']['name']
        try:
            actor = payload['actor']['links']['html']['href']
        except KeyError:
            actor = None

        if ref_type == 'tag':
            committish = ref
        else:
            committish = payload['push']['changes'][0]['new']['target']['hash']
    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(
        copr_id, uuid, clone_url, commits, ref_type, ref, pkg_name
    )

    builds_initiated_via_webhook = []
    for package in packages:
        build = BuildsLogic.rebuild_package(package, {'committish': committish},
                                            submitted_by=actor)
        builds_initiated_via_webhook.append(build)
    add_webhook_history_record(webhook_uuid, user_agent,
                               builds_initiated_via_webhook)

    db.session.commit()

    return "OK", 200


@webhooks_ns.route("/github/<int:copr_id>/<uuid>/", methods=["POST"])
@webhooks_ns.route("/github/<int:copr_id>/<uuid>/<string:pkg_name>/", methods=["POST"])
def webhooks_git_push(copr_id: int, uuid, pkg_name: Optional[str] = None):
    if flask.request.headers["X-GitHub-Event"] == "ping":
        return "OK", 200
    # For the documentation of the data we receive see:
    # https://developer.github.com/v3/activity/events/types/#pushevent
    copr = ComplexLogic.get_copr_by_id(copr_id)
    if copr.webhook_secret != uuid:
        raise AccessRestricted("This webhook is not valid")

    try:
        payload = flask.request.json
        webhook_uuid = flask.request.headers.get("X-GitHub-Delivery")
        user_agent = flask.request.headers.get("User-Agent")
        try:
            clone_url = payload['repository']['clone_url']
        except TypeError:
            return "Missing clone_url in webhook", 400
        commits = []
        payload_commits = payload.get('commits', [])
        for payload_commit in payload_commits:
            commits.append({
                'added': payload_commit['added'],
                'modified': payload_commit['modified'],
                'removed': payload_commit['removed'],
            })

        ref_type = payload.get('ref_type', '')
        ref = payload.get('ref', '')
        try:
            sender = payload['sender']['url']
        except KeyError:
            sender = None
    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(
        copr_id, uuid, clone_url, commits, ref_type, ref, pkg_name
    )

    committish = (ref if ref_type == 'tag' else payload.get('after', ''))
    builds_initiated_via_webhook = []
    for package in packages:
        build = BuildsLogic.rebuild_package(package, {'committish': committish},
                                            submitted_by=sender)
        builds_initiated_via_webhook.append(build)

    add_webhook_history_record(webhook_uuid, user_agent,
                               builds_initiated_via_webhook)
    db.session.commit()

    return "OK", 200


@webhooks_ns.route("/gitlab/<int:copr_id>/<uuid>/", methods=["POST"])
@webhooks_ns.route("/gitlab/<int:copr_id>/<uuid>/<string:pkg_name>/", methods=["POST"])
def webhooks_gitlab_push(copr_id: int, uuid, pkg_name: Optional[str] = None):
    # For the documentation of the data we receive see:
    # https://gitlab.com/help/user/project/integrations/webhooks#events
    copr = ComplexLogic.get_copr_by_id(copr_id)
    if copr.webhook_secret != uuid:
        raise AccessRestricted("This webhook is not valid")

    try:
        webhook_uuid = flask.request.headers.get('X-Gitlab-Webhook-UUID')
        user_agent = flask.request.headers.get('User-Agent')
        payload = flask.request.json
        clone_url = payload['project']['git_http_url']
        commits = []
        payload_commits = payload.get('commits', [])
        for payload_commit in payload_commits:
            commits.append({
                'added': payload_commit['added'],
                'modified': payload_commit['modified'],
                'removed': payload_commit['removed'],
            })
        if payload['object_kind'] == 'tag_push':
            ref_type = 'tag'
            ref = os.path.basename(payload.get('ref', ''))
        else:
            ref_type = None
            ref = payload.get('ref', '')

        try:
            submitter = 'gitlab.com:{}'.format(str(payload["user_username"]))
        except KeyError:
            submitter = None

    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(
        copr_id, uuid, clone_url, commits, ref_type, ref, pkg_name
    )

    committish = (ref if ref_type == 'tag' else payload.get('after', ''))

    builds_initiated_via_webhook = []
    for package in packages:
        build = BuildsLogic.rebuild_package(package, {'committish': committish},
                                            submitted_by=submitter)
        builds_initiated_via_webhook.append(build)
    add_webhook_history_record(webhook_uuid, user_agent,
                               builds_initiated_via_webhook)

    db.session.commit()

    return "OK", 200


class HookContentStorage(object):
    tmp = None

    def __init__(self):
        if not flask.request.get_data():
            return
        self.tmp = tempfile.mkdtemp(dir=app.config["STORAGE_DIR"])
        log.debug("storing hook content under %s", self.tmp)
        try:
            with open(os.path.join(self.tmp, 'hook_payload'), "wb") as f:
                # Do we need to dump http headers, too?
                f.write(flask.request.get_data())

        except Exception:
            log.exception('can not store hook payload')
            self.delete()

    def rebuild_dict(self):
        if self.tmp:
            return {'tmp': os.path.basename(self.tmp), 'hook_data': True }
        return {}

    def delete(self):
        if self.tmp:
            shutil.rmtree(self.tmp)


@webhooks_ns.route("/custom/<int:copr_id>/<uuid>/", methods=["POST"])
@webhooks_ns.route("/custom/<int:copr_id>/<uuid>/<package_name>/", methods=["POST"])
@copr_id_and_uuid_required
@package_name_required
@skip_invalid_calls
def webhooks_package_custom(copr, package):
    return custom_build_submit(copr, package)


@webhooks_ns.route("/custom-dir/<ownername>/<dirname>/<uuid>/<package_name>/", methods=["POST"])
def webhooks_coprdir_custom(ownername, dirname, uuid, package_name):
    """
    Similar to webhooks_package_custom() method, but this gives us a possibility
    to create (or just use) a separated custom directory.
    """
    try:
        copr = CoprsLogic.get_by_ownername_and_dirname(ownername, dirname)
    except ObjectNotFound:
        return "PROJECT_NOT_FOUND\n", 404

    try:
        package = ComplexLogic.get_package(copr, package_name)
    except ObjectNotFound:
        return "PACKAGE_NOT_FOUND\n", 404

    if copr.webhook_secret != uuid:
        return "BAD_UUID\n", 403

    try:
        copr_dir = CoprDirsLogic.get_or_create(copr, dirname)
    except BadRequest:
        return "CANT_CREATE_DIRECTORY\n", 400

    return custom_build_submit(copr, package, copr_dir)


def custom_build_submit(copr, package, copr_dir=None):
    """
    Submit the custom build, let the route argument parsing on callers.
    """
    # Each source provider (github, gitlab, pagure, ...) provides different
    # "payload" format for different events.  Parsing it here is burden we can
    # do one day, but now just dump the hook contents somewhere so users can
    # parse manually.
    storage = HookContentStorage()

    if not copr.active_copr_chroots:
        return "NO_ACTIVE_CHROOTS_IN_PROJECT\n", 500

    try:
        build = BuildsLogic.rebuild_package(package, storage.rebuild_dict(),
                                            copr_dir=copr_dir)
        db.session.commit()
    except Exception:
        log.exception('can not submit build from webhook')
        storage.delete()
        return "BUILD_REQUEST_ERROR\n", 500

    user_agent = flask.request.headers.get('User-Agent')
    add_webhook_history_record(None, user_agent, [build])

    # Return the build ID, so (e.g.) the CI process (e.g. Travis job) knows
    # what build results to wait for.
    return str(build.id) + "\n", 200
