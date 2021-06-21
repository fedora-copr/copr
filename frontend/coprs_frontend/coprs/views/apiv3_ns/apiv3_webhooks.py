"""
APIv3 endpoints related to webhooks
"""

import flask
from coprs import db
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import editable_copr, POST
from coprs.views.apiv3_ns import apiv3_ns


def to_dict(copr):
    """
    Convert `models.Copr` object to an APIv3 representation of
    webhook-related data
    """
    return {
        "id": copr.id,
        "name": copr.name,
        "ownername": copr.owner_name,
        "full_name": copr.full_name,
        "webhook_secret": copr.webhook_secret
    }


@apiv3_ns.route("/webhook/generate/<ownername>/<projectname>", methods=POST)
@api_login_required
@editable_copr
def new_webhook_secret(copr):
    """
    Generate a new webhook secret for a given project.
    Not an additional secret, though. The previous secret gets lost.
    """
    copr.new_webhook_secret()
    db.session.add(copr)
    db.session.commit()
    return flask.jsonify(to_dict(copr))
