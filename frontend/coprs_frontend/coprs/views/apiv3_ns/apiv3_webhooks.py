"""
APIv3 endpoints related to webhooks
"""

# pylint: disable=missing-class-docstring


from http import HTTPStatus

from flask_restx import Namespace, Resource

from coprs import db
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import api, editable_copr
from coprs.views.apiv3_ns.schema.schemas import fullname_params, webhook_secret_model


apiv3_webhooks_ns = Namespace("webhook", description="Webhooks")
api.add_namespace(apiv3_webhooks_ns)


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


@apiv3_webhooks_ns.route("/generate/<ownername>/<projectname>")
class WebhookSecret(Resource):
    @api_login_required
    @editable_copr
    @apiv3_webhooks_ns.doc(params=fullname_params)
    @apiv3_webhooks_ns.marshal_with(webhook_secret_model)
    @apiv3_webhooks_ns.response(HTTPStatus.OK.value, "Webhook secret created")
    @apiv3_webhooks_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, copr):
        """
        Generate a new webhook secret for a given project.
        Not an additional secret, though. The previous secret gets lost.
        """
        copr.new_webhook_secret()
        db.session.add(copr)
        db.session.commit()
        return to_dict(copr)
