"""
Logic for the notification messages
"""

import time
from coprs import db
from coprs import models
from copr_common.enums import NotificationTypeEnum


class NotificationsLogic:
    """
    Notification Messags Logic
    """

    @classmethod
    def create(cls, user, subject, text, notification_type):
        """
        Create a new notification message for a user
        """
        notification = models.Notification(
            user_id=user.id,
            notification_type=NotificationTypeEnum(notification_type),
            subject=subject,
            body=text,
            created_on=int(time.time()),
        )
        db.session.add(notification)
        return notification

    @classmethod
    def get_unseen_user_notifications(cls, user):
        """
        Query a user's unseen notification messages (newest first)
        """
        return (models.Notification.query
                .filter(models.Notification.user_id == user.id)
                .filter(models.Notification.seen_on.is_(None))
                .order_by(models.Notification.created_on.desc(),
                         models.Notification.id.desc()))

    @classmethod
    def unseen_count(cls, user):
        """
        Count of all unseen messages
        """
        return user.unseen_notifications_count

    @classmethod
    def mark_seen(cls, notification):
        """
        Mark a single notification message as seen.
        """
        if not notification.seen_on:
            notification.seen_on = int(time.time())

    @classmethod
    def mark_seen_by_ids(cls, user, notification_ids):
        """
        Mark notification messages as seen by id's.
        """
        notifications = (models.Notification.query
                         .filter(models.Notification.user_id == user.id)
                         .filter(models.Notification.id.in_(notification_ids)))
        for notification in notifications:
            cls.mark_seen(notification)
