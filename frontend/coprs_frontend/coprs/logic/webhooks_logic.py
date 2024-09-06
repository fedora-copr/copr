"""
    Module for Webhooks History related backend logic.
"""

from coprs import db, models
class WebhooksLogic:
    """
        Class to retrieve Webhook History records from database.
    """
    @classmethod
    def get_all_webhooks(cls, copr):
        """
        Returns all webhooks received for a copr in newest first order.
        """
        builds = (db.session.query(models.Build).join(models.WebhookHistory)
                            .filter(models.Build.webhook_history is not None,
                                    models.Build.copr_id == copr.id).all())

        #Remove any duplicates from the webhook history list.
        webhook_history = {x.webhook_history for x in builds}

        return webhook_history
