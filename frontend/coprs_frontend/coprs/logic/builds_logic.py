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
from sqlalchemy.sql import false,true
from werkzeug.utils import secure_filename
from sqlalchemy import desc,asc, bindparam, Integer
from collections import defaultdict

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
from coprs.logic.actions_logic import ActionsLogic
from coprs.models import BuildChroot,Build,Package,MockChroot
from .coprs_logic import MockChrootsLogic

log = app.logger


class BuildsLogic(object):
    @classmethod
    def get(cls, build_id):
        return models.Build.query.filter(models.Build.id == build_id)

    # todo: move methods operating with BuildChroot to BuildChrootLogic
    @classmethod
    def get_build_tasks(cls, status, background=None):
        """ Returns tasks with given status. If background is specified then
            returns normal jobs (false) or background jobs (true)
        """
        result = models.BuildChroot.query.join(models.Build)\
            .filter(models.BuildChroot.status == status)\
            .order_by(models.BuildChroot.build_id.asc())
        if background is not None:
            result = result.filter(models.Build.is_background == (true() if background else false()))
        return result

    @classmethod
    def get_recent_tasks(cls, user=None, limit=None):
        if not limit:
            limit = 100

        query = models.Build.query
        if user is not None:
            query = query.filter(models.Build.user_id == user.id)

        query = query.join(
            models.BuildChroot.query
                .filter(models.BuildChroot.ended_on.isnot(None))
                .order_by(models.BuildChroot.ended_on.desc())
                .subquery()
        ).order_by(models.Build.id.desc())

        # Workaround - otherwise it could take less records than `limit`even though there are more of them.
        query = query.limit(limit if limit > 100 else 100)
        return list(query.all()[:4])

    @classmethod
    def get_build_importing_queue(cls):
        """
        Returns Builds which are waiting to be uploaded to dist git
        """
        query = (models.Build.query.join(models.BuildChroot)
                 .filter(models.Build.canceled == false())
                 .filter(models.BuildChroot.status == helpers.StatusEnum("importing"))
                 .filter(models.Build.srpm_url.isnot(None))
                )
        query = query.order_by(models.BuildChroot.build_id.asc())
        return query

    @classmethod
    def get_build_task_queue(cls, is_background=False): # deprecated
        """
        Returns BuildChroots which are - waiting to be built or
                                       - older than 2 hours and unfinished
        """
        # todo: filter out build without package
        query = (models.BuildChroot.query.join(models.Build)
                 .filter(models.Build.canceled == false())
                 .filter(models.Build.is_background == (true() if is_background else false()))
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
                         # # todo: we need to be sure that correct `failed` set is set together with `ended_on`
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
    def select_srpm_build_tasks_base_query(cls):
        return (models.Build.query.join(models.BuildChroot)
                .filter(models.Build.srpm_url.is_(None))
                .filter(models.Build.canceled == false())
                .filter(models.BuildChroot.status == helpers.StatusEnum("importing"))
                .filter(or_(
                    models.Build.last_deferred.is_(None),
                    models.Build.last_deferred < int(time.time() - app.config["DEFER_BUILD_SECONDS"])
                )))

    @classmethod
    def select_srpm_build_task(cls, provide_task_ids=[], exclude_owners=[]):
        selected_srpm_build_tasks = (cls.select_srpm_build_tasks_base_query()
                                     .order_by(models.Build.is_background.asc(), models.Build.id.asc())).all()

        for task in selected_srpm_build_tasks:
            if task.task_id in provide_task_ids:
                return task

            owner_name = task.copr.owner_name
            if owner_name in exclude_owners:
                continue

            return task

        return None

    @classmethod
    def select_build_tasks_base_query(cls):
        return (models.BuildChroot.query.join(models.Build)
                .filter(models.Build.canceled == false())
                .filter(or_(
                    models.BuildChroot.status == helpers.StatusEnum("pending"),
                    and_(
                        models.BuildChroot.status == helpers.StatusEnum("running"),
                        models.BuildChroot.started_on < int(time.time() - 1.1 * MAX_BUILD_TIMEOUT),
                        models.BuildChroot.ended_on.is_(None)
                    )
                ))
                .filter(or_(
                    models.BuildChroot.last_deferred.is_(None),
                    models.BuildChroot.last_deferred < int(time.time() - app.config["DEFER_BUILD_SECONDS"])
                )))

    @classmethod
    def select_build_task(cls, provide_task_ids=[], exclude_owners=[], exclude_archs=[], exclude_owner_arch_pairs=[]):
        selected_build_tasks = (cls.select_build_tasks_base_query()
                                .order_by(models.Build.is_background.asc(), models.BuildChroot.build_id.asc())).all()

        for task in selected_build_tasks:
            if task.task_id in provide_task_ids:
                return task

            owner_name = task.build.copr.owner_name
            arch = task.mock_chroot.arch
            if owner_name in exclude_owners or arch in exclude_archs \
                    or (owner_name, arch) in exclude_owner_arch_pairs:
                continue

            return task

        return None

    @classmethod
    def get_build_task(cls, task_id):
        try:
            build_id, chroot_name = task_id.split("-", 1)
        except ValueError:
            raise MalformedArgumentException("Invalid task_id {}".format(task_id))

        build_chroot = BuildChrootsLogic.get_by_build_id_and_name(build_id, chroot_name)
        return build_chroot.join(models.Build).first()

    @classmethod
    def get_srpm_build_task(cls, build_id):
        return BuildsLogic.get_by_id(build_id).first()

    @classmethod
    def get_multiple(cls):
        return models.Build.query.order_by(models.Build.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        """ Get collection of builds in copr sorted by build_id descending
        """
        return cls.get_multiple().filter(models.Build.copr == copr)

    @classmethod
    def get_multiple_by_user(cls, user):
        """ Get collection of builds in copr sorted by build_id descending
        form the copr belonging to `user`
        """
        return cls.get_multiple().join(models.Build.copr).filter(
            models.Copr.user == user)


    @classmethod
    def init_db(cls):
        if db.engine.url.drivername == "sqlite":
            return

        status_to_order = """
        CREATE OR REPLACE FUNCTION status_to_order (x integer)
        RETURNS integer AS $$ BEGIN
                RETURN CASE WHEN x = 0 THEN 0
                            WHEN x = 3 THEN 1
                            WHEN x = 6 THEN 2
                            WHEN x = 7 THEN 3
                            WHEN x = 4 THEN 4
                            WHEN x = 1 THEN 5
                            WHEN x = 5 THEN 6
                       ELSE 1000
                END; END;
            $$ LANGUAGE plpgsql;
        """

        order_to_status = """
        CREATE OR REPLACE FUNCTION order_to_status (x integer)
        RETURNS integer AS $$ BEGIN
                RETURN CASE WHEN x = 0 THEN 0
                            WHEN x = 1 THEN 3
                            WHEN x = 2 THEN 6
                            WHEN x = 3 THEN 7
                            WHEN x = 4 THEN 4
                            WHEN x = 5 THEN 1
                            WHEN x = 6 THEN 5
                       ELSE 1000
                END; END;
            $$ LANGUAGE plpgsql;
        """

        db.engine.connect()
        db.engine.execute(status_to_order)
        db.engine.execute(order_to_status)

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
    ON copr.user_id = "user".id
LEFT OUTER JOIN "group"
    ON copr.group_id = "group".id
WHERE build.copr_id = :copr_id
GROUP BY
    build.id;
"""

        if db.engine.url.drivername == "sqlite":
            def sqlite_status_to_order(x):
                if x == 3:
                    return 1
                elif x == 6:
                    return 2
                elif x == 7:
                    return 3
                elif x == 4:
                    return 4
                elif x == 0:
                    return 5
                elif x == 1:
                    return 6
                elif x == 5:
                    return 7
                elif x == 8:
                    return 8
                return 1000

            def sqlite_order_to_status(x):
                if x == 1:
                    return 3
                elif x == 2:
                    return 6
                elif x == 3:
                    return 7
                elif x == 4:
                    return 4
                elif x == 5:
                    return 0
                elif x == 6:
                    return 1
                elif x == 7:
                    return 5
                elif x == 8:
                    return 8
                return 1000

            conn = db.engine.connect()
            conn.connection.create_function("status_to_order", 1, sqlite_status_to_order)
            conn.connection.create_function("order_to_status", 1, sqlite_order_to_status)
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            result = conn.execute(statement, {"copr_id": copr.id})
        else:
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            result = db.engine.execute(statement, {"copr_id": copr.id})

        return result

    @classmethod
    def join_group(cls, query):
        return query.join(models.Copr).outerjoin(models.Group)

    @classmethod
    def get_multiple_by_name(cls, username, coprname):
        query = cls.get_multiple()
        return (query.join(models.Build.copr)
                .options(db.contains_eager(models.Build.copr))
                .join(models.Copr.user)
                .filter(models.Copr.name == coprname)
                .filter(models.User.username == username))

    @classmethod
    def get_importing(cls):
        """
        Return builds that are waiting for dist git to import the sources.
        """
        query = (models.Build.query.join(models.Build.copr)
                 .join(models.User)
                 .join(models.BuildChroot)
                 .options(db.contains_eager(models.Build.copr))
                 .options(db.contains_eager("copr.user"))
                 .filter((models.BuildChroot.started_on == None)
                         | (models.BuildChroot.started_on < int(time.time() - 7200)))
                 .filter(models.BuildChroot.ended_on == None)
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
                 .options(db.contains_eager("copr.user"))
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
        skip_import = False
        git_hashes = {}

        if source_build.source_type == helpers.BuildSourceEnum('upload'):
            # I don't have the source
            # so I don't want to import anything, just rebuild what's in dist git
            skip_import = True

            for chroot in source_build.build_chroots:
                if not chroot.git_hash:
                    # I got an old build from time we didn't use dist git
                    # So I'll submit it as a new build using it's link
                    skip_import = False
                    git_hashes = None
                    flask.flash("This build is not in Dist Git. Trying to import the package again.")
                    break
                git_hashes[chroot.name] = chroot.git_hash

        build = cls.create_new(user, copr, source_build.source_type, source_build.source_json, chroot_names,
                                    pkgs=source_build.pkgs, git_hashes=git_hashes, skip_import=skip_import,
                                    srpm_url=source_build.srpm_url, **build_options)
        build.package_id = source_build.package_id
        build.pkg_version = source_build.pkg_version
        return build

    @classmethod
    def create_new_from_url(cls, user, copr, url,
                            chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("link")
        source_json = json.dumps({"url": url})
        srpm_url = None if url.endswith('.spec') else url
        return cls.create_new(user, copr, source_type, source_json, chroot_names,
                              pkgs=url, srpm_url=srpm_url, **build_options)

    @classmethod
    def create_new_from_scm(cls, user, copr, scm_type, clone_url,
                            committish='', subdirectory='', spec='', srpm_build_method='rpkg',
                            chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("scm")
        source_json = json.dumps({"type": scm_type,
                                  "clone_url": clone_url,
                                  "committish": committish,
                                  "subdirectory": subdirectory,
                                  "spec": spec,
                                  "srpm_build_method": srpm_build_method})
        return cls.create_new(user, copr, source_type, source_json, chroot_names, **build_options)

    @classmethod
    def create_new_from_pypi(cls, user, copr, pypi_package_name, pypi_package_version, python_versions,
                             chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :type package_name: str
        :type version: str
        :type python_versions: List[str]

        :type chroot_names: List[str]

        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("pypi")
        source_json = json.dumps({"pypi_package_name": pypi_package_name,
                                  "pypi_package_version": pypi_package_version,
                                  "python_versions": python_versions})
        return cls.create_new(user, copr, source_type, source_json, chroot_names, **build_options)

    @classmethod
    def create_new_from_rubygems(cls, user, copr, gem_name,
                                 chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :type gem_name: str
        :type chroot_names: List[str]
        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("rubygems")
        source_json = json.dumps({"gem_name": gem_name})
        return cls.create_new(user, copr, source_type, source_json, chroot_names, **build_options)

    @classmethod
    def create_new_from_upload(cls, user, copr, f_uploader, orig_filename,
                               chroot_names=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :param f_uploader(file_path): function which stores data at the given `file_path`
        :return:
        """
        tmp = tempfile.mkdtemp(dir=app.config["STORAGE_DIR"])
        tmp_name = os.path.basename(tmp)
        filename = secure_filename(orig_filename)
        file_path = os.path.join(tmp, filename)
        f_uploader(file_path)

        # make the pkg public
        pkg_url = "{baseurl}/tmp/{tmp_dir}/{filename}".format(
            baseurl=app.config["PUBLIC_COPR_BASE_URL"],
            tmp_dir=tmp_name,
            filename=filename)

        # create json describing the build source
        source_type = helpers.BuildSourceEnum("upload")
        source_json = json.dumps({"url": pkg_url, "pkg": filename, "tmp": tmp_name})
        srpm_url = None if pkg_url.endswith('.spec') else pkg_url

        try:
            build = cls.create_new(user, copr, source_type, source_json,
                                   chroot_names, pkgs=pkg_url, srpm_url=srpm_url, **build_options)
        except Exception:
            shutil.rmtree(tmp)  # todo: maybe we should delete in some cleanup procedure?
            raise

        return build

    @classmethod
    def create_new(cls, user, copr, source_type, source_json, chroot_names=None, pkgs="",
                   git_hashes=None, skip_import=False, background=False, batch=None,
                   srpm_url=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :type chroot_names: List[str]
        :type source_type: int value from helpers.BuildSourceEnum
        :type source_json: str in json format
        :type pkgs: str
        :type git_hashes: dict
        :type skip_import: bool
        :type background: bool
        :type batch: models.Batch
        :rtype: models.Build
        """
        if chroot_names is None:
            chroots = [c for c in copr.active_chroots]
        else:
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        build = cls.add(
            user=user,
            pkgs=pkgs,
            copr=copr,
            chroots=chroots,
            source_type=source_type,
            source_json=source_json,
            enable_net=build_options.get("enable_net", copr.build_enable_net),
            background=background,
            git_hashes=git_hashes,
            skip_import=skip_import,
            batch=batch,
            srpm_url=srpm_url,
        )

        if user.proven:
            if "timeout" in build_options:
                build.timeout = build_options["timeout"]

        return build

    @classmethod
    def add(cls, user, pkgs, copr, source_type=None, source_json=None,
            repos=None, chroots=None, timeout=None, enable_net=True,
            git_hashes=None, skip_import=False, background=False, batch=None,
            srpm_url=None):
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
        if pkgs and (" " in pkgs or "\n" in pkgs or "\t" in pkgs or pkgs.strip() != pkgs):
            raise exceptions.MalformedArgumentException("Trying to create a build using src_pkg "
                                                        "with bad characters. Forgot to split?")

        # just temporary to keep compatibility
        if not source_type or not source_json:
            source_type = helpers.BuildSourceEnum("link")
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
            is_background=bool(background),
            batch=batch,
            srpm_url=srpm_url,
        )

        if timeout:
            build.timeout = timeout or DEFAULT_BUILD_TIMEOUT

        db.session.add(build)

        # add BuildChroot object for each active (or selected) chroot
        # this copr is assigned to
        if not chroots:
            chroots = copr.active_chroots

        if skip_import:
            status = StatusEnum("pending")
        else:
            status = StatusEnum("importing")

        for chroot in chroots:
            git_hash = None
            if git_hashes:
                git_hash = git_hashes.get(chroot.name)
            buildchroot = models.BuildChroot(
                build=build,
                status=status,
                mock_chroot=chroot,
                git_hash=git_hash,
            )
            db.session.add(buildchroot)

        return build

    @classmethod
    def rebuild_package(cls, package, source_dict_update={}):
        source_dict = package.source_json_dict
        source_dict.update(source_dict_update)
        source_json = json.dumps(source_dict)

        build = models.Build(
            user=None,
            pkgs=None,
            package_id=package.id,
            copr=package.copr,
            repos=package.copr.repos,
            source_type=package.source_type,
            source_json=source_json,
            submitted_on=int(time.time()),
            enable_net=package.copr.build_enable_net,
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
    def get_buildchroots_by_build_id_and_branch(cls, build_id, branch):
        """
        Returns a list of BuildChroots identified by build_id and dist-git
        branch name.
        """
        return (
            models.BuildChroot.query
            .join(models.MockChroot)
            .filter(models.BuildChroot.build_id==build_id)
            .filter(models.MockChroot.distgit_branch_name==branch)
        ).all()


    @classmethod
    def delete_local_source(cls, build):
        """
        Deletes the locally stored data for build purposes.  This is typically
        uploaded srpm file, uploaded spec file or webhook POST content.
        """
        # is it hosted on the copr frontend?
        data = json.loads(build.source_json)
        if 'tmp' in data:
            tmp = data["tmp"]
            storage_path = app.config["STORAGE_DIR"]
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
            if upd_dict["chroot"] == "srpm-builds":

                if "last_deferred" in upd_dict:
                    build.last_deferred = upd_dict["last_deferred"]

                if upd_dict.get("status") == StatusEnum("failed") and not build.canceled:
                    build.fail_type = helpers.FailTypeEnum("srpm_build_error")
                    for ch in build.build_chroots:
                        ch.status = helpers.StatusEnum("failed")
                        ch.ended_on = upd_dict.get("ended_on") or time.time()
                        db.session.add(ch)

            # update respective chroot status
            for build_chroot in build.build_chroots:
                if build_chroot.name == upd_dict["chroot"]:

                    if "status" in upd_dict and build_chroot.status not in BuildsLogic.terminal_states:
                        build_chroot.status = upd_dict["status"]

                    if upd_dict.get("status") in BuildsLogic.terminal_states:
                        build_chroot.ended_on = upd_dict.get("ended_on") or time.time()

                    if upd_dict.get("status") == StatusEnum("starting"):
                        build_chroot.started_on = upd_dict.get("started_on") or time.time()

                    if "last_deferred" in upd_dict:
                        build.last_deferred = upd_dict["last_deferred"]

                    db.session.add(build_chroot)

                    # If the last package of a module was successfully built,
                    # then send an action to create module repodata on backend
                    if (build.module
                            and upd_dict.get("status") == StatusEnum("succeeded")
                            and all(b.status == StatusEnum("succeeded") for b in build.module.builds)):
                        ActionsLogic.send_build_module(build.copr, build.module)

        for attr in ["results", "built_packages", "srpm_url"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(build, attr, value)

        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to cancel this build.")
        if not build.cancelable:
            if build.status == StatusEnum("starting"):
                err_msg = "Cannot cancel build {} in state 'starting'".format(build.id)
            else:
                err_msg = "Cannot cancel build {}".format(build.id)
            raise exceptions.RequestCannotBeExecuted(err_msg)

        if build.status == StatusEnum("running"): # otherwise the build is just in frontend
            ActionsLogic.send_cancel_build(build)

        build.canceled = True
        for chroot in build.build_chroots:
            chroot.status = 2  # canceled
            if chroot.ended_on is not None:
                chroot.ended_on = time.time()

    @classmethod
    def delete_build(cls, user, build, send_delete_action=True):
        """
        :type user: models.User
        :type build: models.Build
        """
        if not user.can_edit(build.copr) or build.persistent:
            raise exceptions.InsufficientRightsException(
                "You are not allowed to delete build `{}`.".format(build.id))

        if not build.finished:
            # from celery.contrib import rdb; rdb.set_trace()
            raise exceptions.ActionInProgressException(
                "You can not delete build `{}` which is not finished.".format(build.id),
                "Unfinished build")

        if send_delete_action:
            ActionsLogic.send_delete_build(build)

        for build_chroot in build.build_chroots:
            db.session.delete(build_chroot)
        db.session.delete(build)

    @classmethod
    def mark_as_failed(cls, build_id):
        """
        Marks build as failed on all its non-finished chroots
        """
        build = cls.get(build_id).one()
        chroots = filter(lambda x: x.status != helpers.StatusEnum("succeeded"), build.build_chroots)
        for chroot in chroots:
            chroot.status = helpers.StatusEnum("failed")
        return build

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
            .filter(models.BuildChroot.ended_on.isnot(None))
            .order_by(models.BuildChroot.ended_on.desc())
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
            return query.join(models.BuildChroot).filter(models.BuildChroot.ended_on.isnot(None))
        else:
            return query.join(models.BuildChroot).filter(models.BuildChroot.ended_on.is_(None))

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
            .join(models.Copr.user)
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
    def filter_by_project_user_name(cls, query, username):
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
        query = """
	SELECT
	  package.id as package_id,
	  package.name AS package_name,
	  build.id AS build_id,
	  build_chroot.status AS build_chroot_status,
	  build.pkg_version AS build_pkg_version,
	  mock_chroot.id AS mock_chroot_id,
          mock_chroot.os_release AS mock_chroot_os_release,
          mock_chroot.os_version AS mock_chroot_os_version,
          mock_chroot.arch AS mock_chroot_arch
	FROM package
	JOIN (SELECT
	  MAX(build.id) AS max_build_id_for_chroot,
	  build.package_id AS package_id,
	  build_chroot.mock_chroot_id AS mock_chroot_id
	FROM build
	JOIN build_chroot
	  ON build.id = build_chroot.build_id
	WHERE build.copr_id = {copr_id}
	AND build_chroot.status != 2
	GROUP BY build.package_id,
		 build_chroot.mock_chroot_id) AS max_build_ids_for_a_chroot
	  ON package.id = max_build_ids_for_a_chroot.package_id
	JOIN build
	  ON build.id = max_build_ids_for_a_chroot.max_build_id_for_chroot
	JOIN build_chroot
	  ON build_chroot.mock_chroot_id = max_build_ids_for_a_chroot.mock_chroot_id
	  AND build_chroot.build_id = max_build_ids_for_a_chroot.max_build_id_for_chroot
	JOIN mock_chroot
	  ON mock_chroot.id = max_build_ids_for_a_chroot.mock_chroot_id
	ORDER BY package.name ASC, package.id ASC, mock_chroot.os_release ASC, mock_chroot.os_version ASC, mock_chroot.arch ASC
	""".format(copr_id=copr.id)
        rows = db.session.execute(query)
        return rows
