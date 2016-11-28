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
def webhooks_hello(copr_id, uuid):
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
        clone_url = payload["repository"]["clone_url"]
    except KeyError:
        return "Bad Request", 400

    packages = PackagesLogic.get_for_webhook_rebuild(copr_id, uuid, clone_url, payload)

    for package in packages:
        BuildsLogic.rebuild_package(package)

    db.session.commit()

    return "OK", 200

