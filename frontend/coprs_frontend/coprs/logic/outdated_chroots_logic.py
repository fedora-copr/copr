import flask
from datetime import datetime, timedelta
from sqlalchemy import not_
from coprs import db
from coprs import app
from coprs import models
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprChrootsLogic


class OutdatedChrootsLogic:
    @classmethod
    def has_not_reviewed(cls, user):
        """
        Does a user have some projects with newly outdated chroots that he
        hasn't reviewed yet?
        """
        projects = ComplexLogic.get_coprs_permissible_by_user(user)
        projects_ids = [p.id for p in projects]
        period = app.config["EOL_CHROOTS_NOTIFICATION_PERIOD"]
        now = datetime.now()
        soon = now + timedelta(days=period)

        reviewed = [x.copr_chroot_id for x in cls.get_all_reviews(user).all()]
        return bool((models.CoprChroot.query.join(models.CoprChroot.mock_chroot)
                     .filter(models.CoprChroot.copr_id.in_(projects_ids))
                     .filter(models.CoprChroot.delete_after.isnot(None))
                     .filter(models.CoprChroot.delete_after <= soon)
                     .filter(models.CoprChroot.delete_after > now)
                     .filter(models.CoprChroot.id.notin_(reviewed))
                     .filter(not_(models.MockChroot.is_active))
                     .first()))

    @classmethod
    def get_all_reviews(cls, user):
        """
        Query all outdated chroots that a user has already seen
        """
        return (models.ReviewedOutdatedChroot.query
                .filter(models.ReviewedOutdatedChroot.user_id == user.id))

    @classmethod
    def make_review(cls, user):
        """
        A `user` declares that he has seen and reviewed all outdated chroots in
        all of his projects (i.e. this method creates `ReviewedOutdatedChroot`
        results for all of them)
        """
        reviews = {x.copr_chroot_id for x in cls.get_all_reviews(user)}
        for copr in ComplexLogic.get_coprs_permissible_by_user(user):
            for chroot in copr.outdated_chroots:
                if chroot.id in reviews:
                    continue

                period = app.config["EOL_CHROOTS_NOTIFICATION_PERIOD"]
                if chroot.delete_after_days > period:
                    continue

                review = models.ReviewedOutdatedChroot(
                    user_id=user.id,
                    copr_chroot_id=chroot.id,
                )
                db.session.add(review)

    @classmethod
    def extend(cls, copr_chroot):
        """
        A `user` decided to extend the preservation period for some EOL chroot
        """
        delete_after_days = app.config["DELETE_EOL_CHROOTS_AFTER"]
        cls._update_copr_chroot(copr_chroot, delete_after_days)
        (models.ReviewedOutdatedChroot.query
         .filter(models.ReviewedOutdatedChroot.copr_chroot_id
                 == copr_chroot.id)).delete()

    @classmethod
    def expire(cls, copr_chroot):
        """
        A `user` decided to expire some EOL chroot,
        i.e. its data should be deleted ASAP
        """
        delete_after_days = app.config["EOL_CHROOTS_EXPIRE_PERIOD"]

        # User manually clicked the "Expire now" button, we can assume he has
        # been notified by this action
        copr_chroot.delete_notify = datetime.now()

        cls._update_copr_chroot(copr_chroot, delete_after_days)

    @classmethod
    def _update_copr_chroot(cls, copr_chroot, delete_after_days, actor=None):
        delete_after_timestamp = (
            datetime.now()
            + timedelta(days=delete_after_days)
        )

        if actor is None:
            actor = flask.g.user

        CoprChrootsLogic.update_chroot(actor, copr_chroot,
                                       delete_after=delete_after_timestamp)


    @classmethod
    def trigger_rolling_eol_policy(cls):
        """
        Go through all the MockChroot.rolling -> CoprChroots, and check when the
        last build has been done.  If it is more than
        config.ROLLING_CHROOTS_INACTIVITY_WARNING days, mark the CoprChroot for
        removal after ROLLING_CHROOTS_INACTIVITY_REMOVAL days.
        """

        period = app.config["ROLLING_CHROOTS_INACTIVITY_WARNING"] * 24 * 3600
        warn_timestamp = int(datetime.now().timestamp()) - period

        query = (
            db.session.query(models.CoprChroot).join(models.MockChroot)
            .filter(models.MockChroot.rolling.is_(True))
            .filter(models.MockChroot.is_active.is_(True))
            .filter(models.CoprChroot.delete_after.is_(None))
            .filter(models.CoprChroot.last_build_timestamp.isnot(None))
            .filter(models.CoprChroot.last_build_timestamp < warn_timestamp)
        )

        when = app.config["ROLLING_CHROOTS_INACTIVITY_REMOVAL"]
        for chroot in query:
            cls._update_copr_chroot(chroot, when,
                                    models.AutomationUser("Rolling-Builds-Cleaner"))

        db.session.commit()
