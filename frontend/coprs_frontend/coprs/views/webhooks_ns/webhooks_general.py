import flask

from coprs import db, app
from coprs import helpers

from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.packages_logic import PackagesLogic

from coprs.exceptions import ObjectNotFound, AccessRestricted

from coprs.views.webhooks_ns import webhooks_ns
from coprs.views.misc import page_not_found, access_restricted

import logging
log = logging.getLogger(__name__)


@webhooks_ns.route("/github/<copr_id>/<uuid>/", methods=["POST"])
def webhooks_git_push(copr_id, uuid):
    # For the documentation of the data we receive see:
    # https://developer.github.com/v3/activity/events/types/#pushevent
    try:
        copr = ComplexLogic.get_copr_by_id_safe(copr_id)
    except ObjectNotFound:
        return page_not_found("Project does not exist")

    if copr.webhook_secret != uuid:
        return access_restricted("This webhook is not valid")

    try:
        payload = flask.request.json
        clone_url = payload['repository']['clone_url']
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
    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(copr_id, uuid, clone_url, commits, ref_type, ref)

    for package in packages:
        BuildsLogic.rebuild_package(package)

    db.session.commit()

    return "OK", 200

@webhooks_ns.route("/gitlab/<copr_id>/<uuid>/", methods=["POST"])
def webhooks_gitlab_push(copr_id, uuid):
    # For the documentation of the data we receive see:
    # https://gitlab.com/help/user/project/integrations/webhooks#events
    try:
        copr = ComplexLogic.get_copr_by_id_safe(copr_id)
    except ObjectNotFound:
        return page_not_found("Project does not exist")

    if copr.webhook_secret != uuid:
        return access_restricted("This webhook is not valid")

    try:
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
        else:
            ref_type = None
        ref = payload.get('ref', '')
    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(copr_id, uuid, clone_url, commits, ref_type, ref)

    for package in packages:
        BuildsLogic.rebuild_package(package)

    db.session.commit()

    return "OK", 200

