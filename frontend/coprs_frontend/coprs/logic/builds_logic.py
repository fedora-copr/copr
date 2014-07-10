import time

from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers
from coprs import signals

from coprs.logic import coprs_logic
from coprs.logic import users_logic


class BuildsLogic(object):

    @classmethod
    def get(cls, build_id):
        query = models.Build.query.filter(models.Build.id == build_id)
        return query

    @classmethod
    def get_multiple(cls, user, **kwargs):
        copr = kwargs.get("copr", None)
        username = kwargs.get("username", None)
        coprname = kwargs.get("coprname", None)

        query = models.Build.query.order_by(models.Build.submitted_on.desc())

        # if we get copr, query by its id
        if copr:
            query = query.filter(models.Build.copr == copr)
        elif username and coprname:
            query = (query.join(models.Build.copr)
                     .options(db.contains_eager(models.Build.copr))
                     .join(models.Copr.owner)
                     .filter(models.Copr.name == coprname)
                     .filter(models.User.openid_name ==
                             models.User.openidize_name(username))
                     .order_by(models.Build.submitted_on.desc()))
        else:
            raise exceptions.ArgumentMissingException(
                "Must pass either copr or both coprname and username")

        return query

    @classmethod
    def get_waiting(cls):
        """
        Return builds that aren't both started and finished
        (if build start submission fails, we still want to mark
        the build as non-waiting, if it ended)
        this has very different goal then get_multiple, so implement it alone
        """

        query = (models.Build.query.join(models.Build.copr)
                 .join(models.User)
                 .options(db.contains_eager(models.Build.copr))
                 .options(db.contains_eager("copr.owner"))
                 .filter((models.Build.started_on == None)
                         | (models.Build.started_on < int(time.time() - 7200)))
                 .filter(models.Build.ended_on == None)
                 .filter(models.Build.canceled != True)
                 .order_by(models.Build.submitted_on.asc()))
        return query

    @classmethod
    def get_by_ids(cls, ids):
        return models.Build.query.filter(models.Build.id.in_(ids))

    @classmethod
    def get_by_id(cls, build_id):
        return models.Build.query.get(build_id)

    @classmethod
    def add(cls, user, pkgs, copr,
            repos=None, memory_reqs=None, timeout=None, chroots=None):
        if chroots is None:
            chroots = []
        coprs_logic.CoprsLogic.raise_if_unfinished_blocking_action(
            user, copr,
            "Can't build while there is an operation in progress: {action}")
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        if not repos:
            repos = copr.repos

        build = models.Build(
            user=user,
            pkgs=pkgs,
            copr=copr,
            repos=repos,
            submitted_on=int(time.time()))

        if memory_reqs:
            build.memory_reqs = memory_reqs

        if timeout:
            build.timeout = timeout

        db.session.add(build)

        # add BuildChroot object for each active (or selected) chroot
        # this copr is assigned to
        if not chroots:
            chroots = copr.active_chroots

        for chroot in chroots:
            buildchroot = models.BuildChroot(
                build=build,
                mock_chroot=chroot)

            db.session.add(buildchroot)

        return build

    @classmethod
    def update_state_from_dict(cls, build, upd_dict):
        if "chroot" in upd_dict:
            # update respective chroot status
            for build_chroot in build.build_chroots:
                if build_chroot.name == upd_dict["chroot"]:
                    if "status" in upd_dict:
                        build_chroot.status = upd_dict["status"]

                    db.session.add(build_chroot)

        for attr in ["results", "started_on", "ended_on", "pkg_version", "built_packages"]:
            value = upd_dict.get(attr, None)
            if value:
                # only update started_on once
                if attr == "started_on" and build.started_on:
                    continue

                # update ended_on when everything really ends
                # update results when there is repo initialized for every chroot
                if (attr == "ended_on" and build.has_unfinished_chroot) or \
                   (attr == "results" and build.has_pending_chroot):
                    continue

                if attr == "ended_on":
                    signals.build_finished.send(cls, build=build)

                setattr(build, attr, value)

        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to cancel this build.")
        build.canceled = True
        for chroot in build.build_chroots:
            chroot.status = 2 #canceled

    @classmethod
    def delete_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete this build.")

        if not build.deletable:
            raise exceptions.ActionInProgressException(
                "You can not delete build which is not finished.",
                "Unfinished build")

        # Only failed (and finished), succeeded, skipped and cancelled get here.
        if build.state != "cancelled": #has nothing in backend to delete
            object_type = "build-{0}".format(build.state)
            action = models.Action(action_type=helpers.ActionTypeEnum("delete"),
                               object_type=object_type,
                               object_id=build.id,
                               old_value="{0}/{1}".format(build.copr.owner.name,
                                                          build.copr.name),
                               data=build.pkgs,
                               created_on=int(time.time()))

            db.session.add(action)

        for build_chroot in build.build_chroots:
            db.session.delete(build_chroot)
        db.session.delete(build)

    @classmethod
    def last_modified(cls, copr):
        """ Get build datetime (as epoch) of last successfull build

        :arg copr: object of copr
        """
        builds = cls.get_multiple(None, copr=copr)

        last_build = (builds
                    .join(models.BuildChroot)
                    .filter((models.BuildChroot.status == helpers.StatusEnum("succeeded"))
                          or (models.BuildChroot.status == helpers.StatusEnum("skipped")))
                    .filter(models.Build.ended_on != None)
                    .order_by(models.Build.ended_on.desc())
                    ).first()
        if last_build:
            return last_build.ended_on
        else:
            return None
