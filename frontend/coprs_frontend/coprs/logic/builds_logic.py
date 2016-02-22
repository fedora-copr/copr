from collections import defaultdict
import tempfile
import shutil
import json
import os
import pprint
import time
import flask
import sqlite3
from sqlalchemy.sql import text
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import false
from werkzeug.utils import secure_filename

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers
from coprs.constants import DEFAULT_BUILD_TIMEOUT, MAX_BUILD_TIMEOUT
from coprs.exceptions import MalformedArgumentException, ActionInProgressException, InsufficientRightsException
from coprs.helpers import StatusEnum

from coprs.logic import coprs_logic
from coprs.logic import users_logic
from coprs.logic import packages_logic
from coprs.logic.actions_logic import ActionsLogic
from coprs.models import BuildChroot
from .coprs_logic import MockChrootsLogic

log = app.logger


class BuildsLogic(object):
    @classmethod
    def get(cls, build_id):
        return models.Build.query.filter(models.Build.id == build_id)

    # todo: move methods operating with BuildChroot to BuildChrootLogic
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
    def get_build_importing_queue(cls):
        """
        Returns BuildChroots which are waiting to be uploaded to dist git
        """
        query = (models.BuildChroot.query.join(models.Build)
                 .filter(models.Build.canceled == false())
                 .filter(models.BuildChroot.status == helpers.StatusEnum("importing")))
        query = query.order_by(models.BuildChroot.build_id.asc())
        return query

    @classmethod
    def get_build_task_queue(cls):
        """
        Returns BuildChroots which are - waiting to be built or
                                       - older than 2 hours and unfinished
        """
        # todo: filter out build without package
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
    def get_multiple(cls):
        return models.Build.query.order_by(models.Build.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        """ Get collection of builds in copr sorted by build_id descending
        """
        return cls.get_multiple().filter(models.Build.copr == copr)

    @classmethod
    def get_multiple_by_owner(cls, user):
        """ Get collection of builds in copr sorted by build_id descending
        form the copr owned by `user`
        """
        return cls.get_multiple().join(models.Build.copr).filter(
            models.Copr.owner == user)

    @classmethod
    def get_copr_builds_list(cls, copr):
        query_select = """
SELECT build.id, MAX(package.name) AS pkg_name, build.pkg_version, build.submitted_on,
    MIN(statuses.started_on) AS started_on, MAX(statuses.ended_on) AS ended_on, order_to_status(MIN(statuses.st)) AS status,
    build.canceled, MIN("group".name) AS group_name, MIN(copr.name) as copr_name, MIN("user".username) as user_name
FROM build
LEFT OUTER JOIN package
    ON build.package_id = package.id
LEFT OUTER JOIN (SELECT build_chroot.build_id, started_on, ended_on, status_to_order(status) AS st FROM build_chroot) AS statuses
    ON statuses.build_id=build.id
LEFT OUTER JOIN copr
    ON copr.id = build.copr_id
LEFT OUTER JOIN "user"
    ON copr.owner_id = "user".id
LEFT OUTER JOIN "group"
    ON copr.group_id = "group".id
WHERE build.copr_id = {copr_id}
GROUP BY
    build.id;
""".format(copr_id=copr.id)

        if db.engine.url.drivername == "sqlite":
            def sqlite_status_to_order(x):
                if x == 0:
                    return 0
                elif x == 3:
                    return 1
                elif x == 6:
                    return 2
                elif x == 7:
                    return 3
                elif x == 4:
                    return 4
                elif x == 1:
                    return 5
                elif x == 5:
                    return 6
                return 1000

            def sqlite_order_to_status(x):
                if x == 0:
                    return 0
                elif x == 1:
                    return 3
                elif x == 2:
                    return 6
                elif x == 3:
                    return 7
                elif x == 4:
                    return 4
                elif x == 5:
                    return 1
                elif x == 6:
                    return 5
                return 1000

            conn = db.engine.connect()
            conn.connection.create_function("status_to_order", 1, sqlite_status_to_order)
            conn.connection.create_function("order_to_status", 1, sqlite_order_to_status)
            result = conn.execute(text(query_select))
        else:
            result = db.engine.execute(text(query_select))

        return result

    @classmethod
    def join_group(cls, query):
        return query.join(models.Copr).outerjoin(models.Group)

    @classmethod
    def get_multiple_by_name(cls, username, coprname):
        query = cls.get_multiple()
        return (query.join(models.Build.copr)
                .options(db.contains_eager(models.Build.copr))
                .join(models.Copr.owner)
                .filter(models.Copr.name == coprname)
                .filter(models.User.username == username))

    @classmethod
    def get_importing(cls):
        """
        Return builds that are waiting for dist git to import the sources.
        """
        query = (models.Build.query.join(models.Build.copr)
                 .join(models.User)
                 .options(db.contains_eager(models.Build.copr))
                 .options(db.contains_eager("copr.owner"))
                 .filter((models.Build.started_on == None)
                         | (models.Build.started_on < int(time.time() - 7200)))
                 .filter(models.Build.ended_on == None)
                 .filter(models.Build.canceled == False)
                 .order_by(models.Build.submitted_on.asc()))
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
        return models.Build.query.filter(models.Build.id == build_id)

    @classmethod
    def create_new_from_other_build(cls, user, copr, source_build,
                            chroot_names=None, **build_options):
        # check which chroots we need
        chroots = []
        for chroot in copr.active_chroots:
            if chroot.name in chroot_names:
                chroots.append(chroot)

        # I don't want to import anything, just rebuild what's in dist git
        skip_import = True
        git_hashes = {}
        for chroot in source_build.build_chroots:
            if not chroot.git_hash:
                # I got an old build from time we didn't use dist git
                # So I'll submit it as a new build using it's link
                skip_import = False
                git_hashes = None
                flask.flash("This build is not in Dist Git. Trying to import the package again.")
                break
            git_hashes[chroot.name] = chroot.git_hash

        # try:
        build = cls.add(
            user=user,
            pkgs=source_build.pkgs,
            copr=copr,
            chroots=chroots,
            source_type=source_build.source_type,
            source_json=source_build.source_json,
            enable_net=build_options.get("enable_net", source_build.enable_net),
            git_hashes=git_hashes,
            skip_import=skip_import)

        build.package_id = source_build.package_id
        build.pkg_version = source_build.pkg_version

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build

    @classmethod
    def create_new_from_url(cls, user, copr, srpm_url,
                            chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        if chroot_names is None:
            chroots = [c for c in copr.active_chroots]
        else:
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        source_type = helpers.BuildSourceEnum("srpm_link")
        source_json = json.dumps({"url": srpm_url})

        # try:
        build = cls.add(
            user=user,
            pkgs=srpm_url,
            copr=copr,
            chroots=chroots,
            source_type=source_type,
            source_json=source_json,
            enable_net=build_options.get("enable_net", copr.build_enable_net))

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build

    @classmethod
    def create_new_from_tito(cls, user, copr, git_url, git_dir, git_branch, tito_test,
                            chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        if chroot_names is None:
            chroots = [c for c in copr.active_chroots]
        else:
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        source_type = helpers.BuildSourceEnum("git_and_tito")
        source_json = json.dumps({"git_url": git_url,
                                  "git_dir": git_dir,
                                  "git_branch": git_branch,
                                  "tito_test": tito_test})

        # try:
        build = cls.add(
            user=user,
            pkgs="",
            copr=copr,
            chroots=chroots,
            source_type=source_type,
            source_json=source_json,
            enable_net=build_options.get("enable_net", copr.build_enable_net))

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build

    @classmethod
    def create_new_from_mock(cls, user, copr, scm_type, scm_url, scm_branch, spec,
                             chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        if chroot_names is None:
            chroots = [c for c in copr.active_chroots]
        else:
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        source_type = helpers.BuildSourceEnum("mock_scm")
        source_json = json.dumps({"scm_type": scm_type,
                                  "scm_url": scm_url,
                                  "scm_branch": scm_branch,
                                  "spec": spec})

        # try:
        build = cls.add(
            user=user,
            pkgs="",
            copr=copr,
            chroots=chroots,
            source_type=source_type,
            source_json=source_json,
            enable_net=build_options.get("enable_net", copr.build_enable_net))

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build


    @classmethod
    def create_new_from_pypi(cls, user, copr, pypi_package_name, pypi_package_version, python_version,
                            chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :type package_name: str
        :type version: str
        :type python_version: str

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        if chroot_names is None:
            chroots = [c for c in copr.active_chroots]
        else:
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        source_type = helpers.BuildSourceEnum("pypi")
        source_json = json.dumps({"pypi_package_name": pypi_package_name,
                                  "pypi_package_version": pypi_package_version,
                                  "python_version": python_version})

        build = cls.add(
            user=user,
            pkgs="",
            copr=copr,
            chroots=chroots,
            source_type=source_type,
            source_json=source_json,
            enable_net=build_options.get("enable_net", copr.build_enable_net))

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build

    @classmethod
    def create_new_from_upload(cls, user, copr, f_uploader, orig_filename,
                               chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :param f_uploader(file_path): function which stores data at the given `file_path`
        :return:
        """
        tmp = tempfile.mkdtemp(dir=app.config["SRPM_STORAGE_DIR"])
        tmp_name = os.path.basename(tmp)
        filename = secure_filename(orig_filename)
        file_path = os.path.join(tmp, filename)
        f_uploader(file_path)

        # make the pkg public
        pkg_url = "https://{hostname}/tmp/{tmp_dir}/{srpm}".format(
            hostname=app.config["PUBLIC_COPR_HOSTNAME"],
            tmp_dir=tmp_name,
            srpm=filename)

        # check which chroots we need
        chroots = []
        for chroot in copr.active_chroots:
            if chroot.name in chroot_names:
                chroots.append(chroot)

        # create json describing the build source
        source_type = helpers.BuildSourceEnum("srpm_upload")
        source_json = json.dumps({"tmp": tmp_name, "pkg": filename})
        try:
            build = cls.add(
                user=user,
                pkgs=pkg_url,
                copr=copr,
                chroots=chroots,
                source_type=source_type,
                source_json=source_json,
                enable_net=build_options.get("enable_net", copr.build_enable_net))

            if user.proven:
                if "timeout" in build_options:
                    build.timeout = build_options["timeout"]

        except Exception:
            shutil.rmtree(tmp)  # todo: maybe we should delete in some cleanup procedure?
            raise

        return build

    @classmethod
    def add(cls, user, pkgs, copr, source_type=None, source_json=None,
            repos=None, chroots=None, timeout=None, enable_net=True,
            git_hashes=None, skip_import=False):
        if chroots is None:
            chroots = []

        coprs_logic.CoprsLogic.raise_if_unfinished_blocking_action(
            copr, "Can't build while there is an operation in progress: {action}")
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        if not repos:
            repos = copr.repos

        # todo: eliminate pkgs and this check
        if " " in pkgs or "\n" in pkgs or "\t" in pkgs or pkgs.strip() != pkgs:
            raise exceptions.MalformedArgumentException("Trying to create a build using src_pkg "
                                                        "with bad characters. Forgot to split?")

        # just temporary to keep compatibility
        if not source_type or not source_json:
            source_type = helpers.BuildSourceEnum("srpm_link")
            source_json = json.dumps({"url":pkgs})

        build = models.Build(
            user=user,
            pkgs=pkgs,
            copr=copr,
            repos=repos,
            source_type=source_type,
            source_json=source_json,
            submitted_on=int(time.time()),
            enable_net=bool(enable_net),
        )

        if timeout:
            build.timeout = timeout or DEFAULT_BUILD_TIMEOUT

        db.session.add(build)

        # add BuildChroot object for each active (or selected) chroot
        # this copr is assigned to
        if not chroots:
            chroots = copr.active_chroots

        status = helpers.StatusEnum("importing")

        if skip_import:
            status = StatusEnum("pending")

        for chroot in chroots:
            git_hash = None
            if git_hashes:
                git_hash = git_hashes.get(chroot.name)
            buildchroot = models.BuildChroot(
                build=build,
                status=status,
                mock_chroot=chroot,
                git_hash=git_hash)

            db.session.add(buildchroot)

        return build

    @classmethod
    def rebuild_package(cls, package):
        build = models.Build(
            user=None,
            pkgs=None,
            package_id=package.id,
            copr=package.copr,
            repos=package.copr.repos,
            source_type=package.source_type,
            source_json=package.source_json,
            submitted_on=int(time.time()),
            enable_net=package.enable_net,
            timeout=DEFAULT_BUILD_TIMEOUT
        )

        db.session.add(build)

        chroots = package.copr.active_chroots

        status = helpers.StatusEnum("importing")

        for chroot in chroots:
            buildchroot = models.BuildChroot(
                build=build,
                status=status,
                mock_chroot=chroot,
                git_hash=None
            )

            db.session.add(buildchroot)

        return build


    terminal_states = {StatusEnum("failed"), StatusEnum("succeeded"), StatusEnum("canceled")}

    @classmethod
    def get_chroots_from_dist_git_task_id(cls, task_id):
        """
        Returns a list of BuildChroots identified with task_id
        task_id consists of a name of git branch + build id
        Example: 42-f22 -> build id 42, chroots fedora-22-*
        """
        build_id, branch = task_id.split("-")
        build = cls.get_by_id(build_id).one()
        build_chroots = build.build_chroots
        os, version = helpers.branch_to_os_version(branch)
        chroot_halfname = "{}-{}".format(os, version)
        matching = [ch for ch in build_chroots if chroot_halfname in ch.name]
        return matching


    @classmethod
    def delete_local_srpm(cls, build):
        """
        Deletes the source rpm locally stored for upload (if exists)
        """
        # is it hosted on the copr frontend?
        if build.source_type == helpers.BuildSourceEnum("srpm_upload"):
            data = json.loads(build.source_json)
            tmp = data["tmp"]
            storage_path = app.config["SRPM_STORAGE_DIR"]
            try:
                shutil.rmtree(os.path.join(storage_path, tmp))
            except:
                pass


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

        for attr in ["results", "built_packages"]:
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
        if not build.cancelable:
            raise exceptions.RequestCannotBeExecuted(
                "Cannot cancel build {}".format(build.id))
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
        if not user.can_edit(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete build `{}`.".format(build.id))

        if not build.deletable:
            # from celery.contrib import rdb; rdb.set_trace()
            raise exceptions.ActionInProgressException(
                "You can not delete build `{}` which is not finished.".format(build.id),
                "Unfinished build")

        # Only failed, finished, succeeded  get here.
        if build.state not in ["cancelled"]:  # has nothing in backend to delete
            ActionsLogic.send_delete_build(build)

        for build_chroot in build.build_chroots:
            db.session.delete(build_chroot)
        db.session.delete(build)

    @classmethod
    def last_modified(cls, copr):
        """ Get build datetime (as epoch) of last successful build

        :arg copr: object of copr
        """
        builds = cls.get_multiple_by_copr(copr)

        last_build = (
            builds.join(models.BuildChroot)
            .filter((models.BuildChroot.status == helpers.StatusEnum("succeeded"))
                    | (models.BuildChroot.status == helpers.StatusEnum("skipped")))
            .filter(models.Build.ended_on.isnot(None))
            .order_by(models.Build.ended_on.desc())
        ).first()
        if last_build:
            return last_build.ended_on
        else:
            return None

    @classmethod
    def filter_is_finished(cls, query, is_finished):
        # todo: check that ended_on is set correctly for all cases
        # e.g.: failed dist-git import, cancellation
        if is_finished:
            return query.filter(models.Build.ended_on.isnot(None))
        else:
            return query.filter(models.Build.ended_on.is_(None))

    @classmethod
    def filter_by_group_name(cls, query, group_name):
        return query.filter(models.Group.name == group_name)


class BuildChrootsLogic(object):
    @classmethod
    def get_by_build_id_and_name(cls, build_id, name):
        mc = MockChrootsLogic.get_from_name(name).one()

        return (
            BuildChroot.query
            .filter(BuildChroot.build_id == build_id)
            .filter(BuildChroot.mock_chroot_id == mc.id)
        )

    @classmethod
    def get_multiply(cls):
        query = (
            models.BuildChroot.query
            .join(models.BuildChroot.build)
            .join(models.BuildChroot.mock_chroot)
            .join(models.Build.copr)
            .join(models.Copr.owner)
            .outerjoin(models.Group)
        )
        return query

    @classmethod
    def filter_by_build_id(cls, query, build_id):
        return query.filter(models.Build.id == build_id)

    @classmethod
    def filter_by_project_id(cls, query, project_id):
        return query.filter(models.Copr.id == project_id)

    @classmethod
    def filter_by_project_owner_name(cls, query, username):
        return query.filter(models.User.username == username)

    @classmethod
    def filter_by_state(cls, query, state):
        return query.filter(models.BuildChroot.status == StatusEnum(state))

    @classmethod
    def filter_by_group_name(cls, query, group_name):
        return query.filter(models.Group.name == group_name)


class BuildsMonitorLogic(object):
    @classmethod
    def get_monitor_data(cls, copr):
        copr_packages = sorted(copr.packages, key=lambda pkg: pkg.name)
        packages = []
        for pkg in copr_packages:
            chroots = {}
            for ch in copr.active_chroots:
                # todo: move to ComplexLogic
                query = (
                    models.BuildChroot.query.join(models.Build)
                    .filter(models.Build.package_id == pkg.id)
                    .filter(models.BuildChroot.mock_chroot_id == ch.id)
                    .filter(models.BuildChroot.status != helpers.StatusEnum("canceled")))
                build = query.order_by(models.BuildChroot.build_id.desc()).first()
                chroots[ch.name] = build
            packages.append({"package": pkg, "build_chroots": chroots})
        return packages
