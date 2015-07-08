from collections import defaultdict
import json
import os
import pprint
import time
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.sql import false

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers
from coprs.constants import DEFAULT_BUILD_TIMEOUT, MAX_BUILD_TIMEOUT
from coprs.helpers import StatusEnum

from coprs.logic import coprs_logic
from coprs.logic import users_logic

log = app.logger


class BuildsLogic(object):
    @classmethod
    def get(cls, build_id):
        return models.Build.query.filter(models.Build.id == build_id)

    @classmethod
    def get_build_tasks(cls, status):
        return models.BuildChroot.query.filter(models.BuildChroot.status == status) \
            .order_by(models.BuildChroot.build_id.desc())

    @classmethod
    def get_recent_tasks(cls, user=None, limit=None):
        if not limit:
            limit = 100

        query = models.Build.query \
            .filter(models.Build.ended_on.isnot(None)) \
            .order_by(models.Build.ended_on.desc())

        if user is not None:
            query = query.filter(models.Build.user_id == user.id)

        query = query \
            .order_by(models.Build.id.desc()) \
            .limit(limit)

        return query

    @classmethod
    def get_build_task_queue(cls):
        """
        Returns BuildChroots which are - waiting to be built or
                                       - older than 2 hours and unfinished
        """
        query = (models.BuildChroot.query.join(models.Build)
                 .filter(models.Build.canceled == false())
                 .filter(or_(
                     models.BuildChroot.status == helpers.StatusEnum("pending"),
                     models.BuildChroot.status == helpers.StatusEnum("starting"),
                     and_(
                         # We are moving ended_on to the BuildChroot, now it should be reliable,
                         # so we don't want to reschedule failed chroots
                         # models.BuildChroot.status.in_([
                         # # Bug 1206562 - Cannot delete Copr because it incorrectly thinks
                         # # there are unfinished builds. Solution: `failed` but unfinished
                         # # (ended_on is null) builds should be rescheduled.
                         # # todo: we need to be sure that correct `failed` set is set together wtih `ended_on`
                         # helpers.StatusEnum("running"),
                         # helpers.StatusEnum("failed")
                         #]),
                         models.BuildChroot.status == helpers.StatusEnum("running"),
                         models.BuildChroot.started_on < int(time.time() - 1.1 * MAX_BUILD_TIMEOUT),
                         models.BuildChroot.ended_on.is_(None)
                     ))
        ))
        query = query.order_by(models.BuildChroot.build_id.asc())
        return query

    @classmethod
    def get_multiple(cls, user, **kwargs):
        copr = kwargs.get("copr", None)
        username = kwargs.get("username", None)
        coprname = kwargs.get("coprname", None)

        query = models.Build.query.order_by(models.Build.id.desc())

        # if we get copr, query by its id
        if copr:
            query = query.filter(models.Build.copr == copr)
        elif username and coprname:
            query = (query.join(models.Build.copr)
                     .options(db.contains_eager(models.Build.copr))
                     .join(models.Copr.owner)
                     .filter(models.Copr.name == coprname)
                     .filter(models.User.username == username)
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
                 .join(models.User).join(models.BuildChroot)
                 .options(db.contains_eager(models.Build.copr))
                 .options(db.contains_eager("copr.owner"))
                 .filter((models.BuildChroot.started_on.is_(None))
                         | (models.BuildChroot.started_on < int(time.time() - 7200)))
                 .filter(models.BuildChroot.ended_on.is_(None))
                 .filter(models.Build.canceled == false())
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
            repos=None, chroots=None,
            memory_reqs=None, timeout=None, enable_net=True):
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

        if " " in pkgs or "\n" in pkgs or "\t" in pkgs or pkgs.strip() != pkgs:
            raise exceptions.MalformedArgumentException("Trying to create a build using src_pkg "
                                                        "with bad characters. Forgot to split?")

        build = models.Build(
            user=user,
            pkgs=pkgs,
            copr=copr,
            repos=repos,
            submitted_on=int(time.time()),
            enable_net=bool(enable_net),
        )

        if memory_reqs:
            build.memory_reqs = memory_reqs

        if timeout:
            build.timeout = timeout or DEFAULT_BUILD_TIMEOUT

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

    terminal_states = {StatusEnum("failed"), StatusEnum("succeeded"), StatusEnum("canceled")}

    @classmethod
    def update_state_from_dict(cls, build, upd_dict):
        """
        :param build:
        :param upd_dict:
            example:
            {
              "builds":[
               {
                 "id": 1,
                 "copr_id": 2,
                 "started_on": 139086644000
               },
               {
                 "id": 2,
                 "copr_id": 1,
                 "status": 0,
                 "chroot": "fedora-18-x86_64",
                 "results": "http://server/results/foo/bar/",
                 "ended_on": 139086644000
               }]
            }
        """
        log.info("Updating build: {} by: {}".format(build.id, upd_dict))
        if "chroot" in upd_dict:
            # update respective chroot status
            for build_chroot in build.build_chroots:
                if build_chroot.name == upd_dict["chroot"]:

                    if "status" in upd_dict and build_chroot.status not in BuildsLogic.terminal_states:
                        build_chroot.status = upd_dict["status"]

                    if upd_dict.get("status") in BuildsLogic.terminal_states:
                        build_chroot.ended_on = upd_dict.get("ended_on") or time.time()

                    if upd_dict.get("status") == StatusEnum("starting"):
                        build_chroot.started_on = upd_dict.get("started_on") or time.time()

                    db.session.add(build_chroot)

        for attr in ["results", "pkg_version", "built_packages"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(build, attr, value)

        if build.max_ended_on is not None:
            build.ended_on = build.max_ended_on

        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to cancel this build.")
        build.canceled = True
        for chroot in build.build_chroots:
            chroot.status = 2  # canceled
            if chroot.ended_on is not None:
                chroot.ended_on = time.time()

    @classmethod
    def delete_build(cls, user, build):
        """
        :type user: models.User
        :type build: models.Build
        """
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete build `{}`.".format(build.id))

        if not build.deletable:
            # from celery.contrib import rdb; rdb.set_trace()
            raise exceptions.ActionInProgressException(
                "You can not delete build `{}` which is not finished.".format(build.id),
                "Unfinished build")

        # Only failed, finished, succeeded  get here.
        if build.state not in ["cancelled"]:  # has nothing in backend to delete
            # don't delete skipped chroots
            chroots_to_delete = [
                chroot.name for chroot in build.build_chroots
                if chroot.state not in ["skipped"]
            ]

            if chroots_to_delete and build.src_pkg_name:
                data_dict = {"src_pkg_name": build.src_pkg_name,
                             "username": build.copr.owner.name,
                             "projectname": build.copr.name,
                             "chroots": chroots_to_delete}

                action = models.Action(
                    action_type=helpers.ActionTypeEnum("delete"),
                    object_type="build",
                    object_id=build.id,
                    old_value="{0}/{1}".format(build.copr.owner.name,
                                               build.copr.name),
                    data=json.dumps(data_dict),
                    created_on=int(time.time())
                )
                db.session.add(action)

        for build_chroot in build.build_chroots:
            db.session.delete(build_chroot)
        db.session.delete(build)

    @classmethod
    def last_modified(cls, copr):
        """ Get build datetime (as epoch) of last successful build

        :arg copr: object of copr
        """
        builds = cls.get_multiple(None, copr=copr)

        last_build = (
            builds.join(models.BuildChroot)
            .filter((models.BuildChroot.status == helpers.StatusEnum("succeeded"))
                    | (models.BuildChroot.status == helpers.StatusEnum("skipped")))
            .filter(models.Build.ended_on.is_not(None))
            .order_by(models.Build.ended_on.desc())
        ).first()
        if last_build:
            return last_build.ended_on
        else:
            return None

    @classmethod
    def get_multiply_by_copr(cls, copr):
        """ Get collection of builds in copr sorted by build_id descending

        :arg copr: object of copr
        """
        query = models.Build.query.filter(models.Build.copr == copr) \
            .order_by(models.Build.id.desc())

        return query


class BuildsMonitorLogic(object):
    @classmethod
    def get_monitor_data(cls, copr):
        # builds are sorted by build id descending
        builds = BuildsLogic.get_multiply_by_copr(copr).all()

        chroots = set(chroot.name for chroot in copr.active_chroots)
        if builds:
            latest_build = builds[0]
            chroots.union([chroot.name for chroot in latest_build.build_chroots])
        else:
            latest_build = None

        chroots = sorted(chroots)

        # { pkg_name -> { chroot -> (build_id, pkg_version, status) }}
        build_result_by_pkg_chroot = defaultdict(lambda: defaultdict(lambda: None))

        # collect information about pkg version and build states
        for build in builds:
            chroot_results = {chroot.name: chroot.state for chroot in build.build_chroots}

            pkg = os.path.basename(build.pkgs)
            pkg_name = helpers.parse_package_name(pkg)

            for chroot_name, state in chroot_results.items():
                # set only latest version/state
                if build_result_by_pkg_chroot[pkg_name][chroot_name] is None:
                    build_result_by_pkg_chroot[pkg_name][chroot_name] = (build.id, build.pkg_version, state)

        # "transpose" data to present build status per package
        packages = []
        for pkg_name, chroot_dict in build_result_by_pkg_chroot.items():
            br = []
            try:
                latest_build_id = max([build_id for build_id, pkg_version, state
                                       in chroot_dict.values()])
            except ValueError:
                latest_build_id = None

            for chroot_name in chroots:
                chroot_result = chroot_dict.get(chroot_name)
                if chroot_result:
                    build_id, pkg_version, state = chroot_result
                    br.append((build_id, state, pkg_version, chroot_name))
                else:
                    br.append((latest_build_id, None, None, chroot_name))

            packages.append((pkg_name, br))

        packages.sort()

        result = {
            "builds": builds,
            "chroots": chroots,
            "packages": packages,
            "latest_build": latest_build,
        }
        app.logger.debug("Monitor data: \n{}".format(pprint.pformat(result)))
        return result
