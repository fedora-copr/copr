import tempfile
import shutil
import json
import os
import pprint
import time
import flask
import sqlite3
import requests

from flask import request
from sqlalchemy.sql import text
from sqlalchemy import or_
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import false,true
from werkzeug.utils import secure_filename
from sqlalchemy import desc, asc, bindparam, Integer, String
from collections import defaultdict

from copr_common.enums import FailTypeEnum, StatusEnum
from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs import helpers
from coprs.constants import DEFAULT_BUILD_TIMEOUT, MAX_BUILD_TIMEOUT
from coprs.exceptions import MalformedArgumentException, ActionInProgressException, InsufficientRightsException, UnrepeatableBuildException

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

    @classmethod
    def get_build_tasks(cls, status, background=None):
        """ Returns tasks with given status. If background is specified then
            returns normal jobs (false) or background jobs (true)
        """
        result = models.BuildChroot.query.join(models.Build)\
            .filter(models.BuildChroot.status == status)\
            .order_by(models.Build.id.asc())
        if background is not None:
            result = result.filter(models.Build.is_background == (true() if background else false()))
        return result

    @classmethod
    def get_srpm_build_tasks(cls, status, background=None):
        """ Returns srpm build tasks with given status. If background is
            specified then returns normal jobs (false) or background jobs (true)
        """
        result = models.Build.query\
            .filter(models.Build.source_status == status)\
            .order_by(models.Build.id.asc())
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

        # Workaround - otherwise it could take less records than `limit` even though there are more of them.
        query = query.limit(limit if limit > 100 else 100)
        return list(query.all()[:4])

    @classmethod
    def get_running_tasks_by_time(cls, start, end):
        result = models.BuildChroot.query\
            .filter(models.BuildChroot.ended_on > start)\
            .filter(models.BuildChroot.started_on < end)\
            .order_by(models.BuildChroot.started_on.asc())

        return result

    @classmethod
    def get_running_tasks_from_last_day(cls):
        end = int(time.time())
        start = end - 86399
        step = 3600
        tasks = cls.get_running_tasks_by_time(start, end)
        steps = int(round((end - start) / step + 0.5))
        current_step = 0

        data = [[0] * (steps + 1)]
        data[0][0] = ''
        for t in tasks:
            task = t.to_dict()
            while task['started_on'] > start + step * (current_step + 1):
                current_step += 1
            data[0][current_step + 1] += 1
        return data

    @classmethod
    def get_chroot_histogram(cls, start, end):
        chroots = []
        chroot_query = BuildChroot.query\
            .filter(models.BuildChroot.started_on < end)\
            .filter(models.BuildChroot.ended_on > start)\
            .with_entities(BuildChroot.mock_chroot_id,
                           func.count(BuildChroot.mock_chroot_id))\
            .group_by(BuildChroot.mock_chroot_id)\
            .order_by(BuildChroot.mock_chroot_id)

        for chroot in chroot_query:
            chroots.append([chroot[0], chroot[1]])

        mock_chroots = coprs_logic.MockChrootsLogic.get_multiple()
        for mock_chroot in mock_chroots:
            for l in chroots:
                if l[0] == mock_chroot.id:
                    l[0] = mock_chroot.name

        return chroots

    @classmethod
    def get_tasks_histogram(cls, type, start, end, step):
        start = start - (start % step) # align graph interval to a multiple of step
        end = end - (end % step)
        steps = int((end - start) / step + 0.5)
        data = [['pending'], ['running'], ['avg running'], ['time']]

        result = models.BuildsStatistics.query\
            .filter(models.BuildsStatistics.stat_type == type)\
            .filter(models.BuildsStatistics.time >= start)\
            .filter(models.BuildsStatistics.time <= end)\
            .order_by(models.BuildsStatistics.time)

        for row in result:
            data[0].append(row.pending)
            data[1].append(row.running)

        for i in range(len(data[0]) - 1, steps):
            step_start = start + i * step
            step_end = step_start + step

            query_pending = text("""
                SELECT COUNT(*) as pending
                FROM build_chroot JOIN build on build.id = build_chroot.build_id
                WHERE
                    build.submitted_on < :end
                    AND (
                        build_chroot.started_on > :start
                        OR (build_chroot.started_on is NULL AND build_chroot.status = :status)
                        -- for currently pending builds we need to filter on status=pending because there might be
                        -- failed builds that have started_on=NULL
                    )
                    AND NOT build.canceled
            """)

            query_running = text("""
                SELECT COUNT(*) as running
                FROM build_chroot
                WHERE
                    started_on < :end
                    AND (ended_on > :start OR (ended_on is NULL AND status = :status))
                    -- for currently running builds we need to filter on status=running because there might be failed
                    -- builds that have ended_on=NULL
            """)

            res_pending = db.engine.execute(query_pending, start=step_start, end=step_end,
                                            status=StatusEnum('pending'))
            res_running = db.engine.execute(query_running, start=step_start, end=step_end,
                                            status=StatusEnum('running'))

            pending = res_pending.first().pending
            running = res_running.first().running
            data[0].append(pending)
            data[1].append(running)

            statistic = models.BuildsStatistics(
                time = step_start,
                stat_type = type,
                running = running,
                pending = pending
            )
            db.session.merge(statistic)
            db.session.commit()

        running_total = 0
        for i in range(1, steps + 1):
            running_total += data[1][i]

        data[2].extend([running_total * 1.0 / steps] * (len(data[0]) - 1))

        for i in range(start, end, step):
            data[3].append(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(i)))

        return data

    @classmethod
    def get_build_importing_queue(cls, background=None):
        """
        Returns Builds which are waiting to be uploaded to dist git
        """
        query = (models.Build.query
                 .filter(models.Build.canceled == false())
                 .filter(models.Build.source_status == StatusEnum("importing"))
                 .order_by(models.Build.id.asc()))
        if background is not None:
            query = query.filter(models.Build.is_background == (true() if background else false()))
        return query

    @classmethod
    def get_pending_srpm_build_tasks(cls, background=None):
        query = (models.Build.query
                .filter(models.Build.canceled == false())
                .filter(models.Build.source_status == StatusEnum("pending"))
                .order_by(models.Build.is_background.asc(), models.Build.id.asc()))
        if background is not None:
            query = query.filter(models.Build.is_background == (true() if background else false()))
        return query

    @classmethod
    def get_pending_build_tasks(cls, background=None):
        query = (models.BuildChroot.query.join(models.Build)
                .filter(models.Build.canceled == false())
                .filter(or_(
                    models.BuildChroot.status == StatusEnum("pending"),
                    and_(
                        models.BuildChroot.status == StatusEnum("running"),
                        models.BuildChroot.started_on < int(time.time() - 1.1 * MAX_BUILD_TIMEOUT),
                        models.BuildChroot.ended_on.is_(None)
                    )
                ))
                .order_by(models.Build.is_background.asc(), models.Build.id.asc()))
        if background is not None:
            query = query.filter(models.Build.is_background == (true() if background else false()))
        return query

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
        RETURN CASE WHEN x = 3 THEN 1
                WHEN x = 6 THEN 2
                WHEN x = 7 THEN 3
                WHEN x = 4 THEN 4
                WHEN x = 0 THEN 5
                WHEN x = 1 THEN 6
                WHEN x = 5 THEN 7
                WHEN x = 2 THEN 8
                WHEN x = 8 THEN 9
                WHEN x = 9 THEN 10
            ELSE x
        END; END;
        $$ LANGUAGE plpgsql;
        """

        order_to_status = """
        CREATE OR REPLACE FUNCTION order_to_status (x integer)
        RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 1 THEN 3
                WHEN x = 2 THEN 6
                WHEN x = 3 THEN 7
                WHEN x = 4 THEN 4
                WHEN x = 5 THEN 0
                WHEN x = 6 THEN 1
                WHEN x = 7 THEN 5
                WHEN x = 8 THEN 2
                WHEN x = 9 THEN 8
                WHEN x = 10 THEN 9
            ELSE x
        END; END;
        $$ LANGUAGE plpgsql;
        """

        db.engine.connect()
        db.engine.execute(status_to_order)
        db.engine.execute(order_to_status)

    @classmethod
    def get_copr_builds_list(cls, copr, dirname=''):
        query_select = """
SELECT build.id, build.source_status, MAX(package.name) AS pkg_name, build.pkg_version, build.submitted_on,
    MIN(statuses.started_on) AS started_on, MAX(statuses.ended_on) AS ended_on, order_to_status(MIN(statuses.st)) AS status,
    build.canceled, MIN("group".name) AS group_name, MIN(copr.name) as copr_name, MIN("user".username) as user_name, build.copr_id
FROM build
LEFT OUTER JOIN package
    ON build.package_id = package.id
LEFT OUTER JOIN (SELECT build_chroot.build_id, started_on, ended_on, status_to_order(status) AS st FROM build_chroot) AS statuses
    ON statuses.build_id=build.id
LEFT OUTER JOIN copr
    ON copr.id = build.copr_id
LEFT OUTER JOIN copr_dir
    ON build.copr_dir_id = copr_dir.id
LEFT OUTER JOIN "user"
    ON copr.user_id = "user".id
LEFT OUTER JOIN "group"
    ON copr.group_id = "group".id
WHERE build.copr_id = :copr_id
    AND (:dirname = '' OR :dirname = copr_dir.name)
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
                elif x == 2:
                    return 8
                elif x == 8:
                    return 9
                elif x == 9:
                    return 10
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
                    return 2
                elif x == 9:
                    return 8
                elif x == 10:
                    return 9
                return 1000

            conn = db.engine.connect()
            conn.connection.create_function("status_to_order", 1, sqlite_status_to_order)
            conn.connection.create_function("order_to_status", 1, sqlite_order_to_status)
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            statement.bindparams(bindparam("dirname", String))
            result = conn.execute(statement, {"copr_id": copr.id, "dirname": dirname})
        else:
            statement = text(query_select)
            statement.bindparams(bindparam("copr_id", Integer))
            statement.bindparams(bindparam("dirname", String))
            result = db.engine.execute(statement, {"copr_id": copr.id, "dirname": dirname})

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
            if source_build.repeatable:
                skip_import = True
                for chroot in source_build.build_chroots:
                    git_hashes[chroot.name] = chroot.git_hash
            else:
                raise UnrepeatableBuildException("Build sources were not fully imported into CoprDistGit.")

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
    def create_new_from_pypi(cls, user, copr, pypi_package_name, pypi_package_version, spec_template,
                             python_versions, chroot_names=None, **build_options):
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
                                  "spec_template": spec_template,
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
    def create_new_from_custom(cls, user, copr,
            script, script_chroot=None, script_builddeps=None,
            script_resultdir=None, chroot_names=None, **kwargs):
        """
        :type user: models.User
        :type copr: models.Copr
        :type script: str
        :type script_chroot: str
        :type script_builddeps: str
        :type script_resultdir: str
        :type chroot_names: List[str]
        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("custom")
        source_dict = {
            'script': script,
            'chroot': script_chroot,
            'builddeps': script_builddeps,
            'resultdir': script_resultdir,
        }

        return cls.create_new(user, copr, source_type, json.dumps(source_dict),
                chroot_names, **kwargs)

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

        if skip_import and srpm_url:
            chroot_status = StatusEnum("pending")
            source_status = StatusEnum("succeeded")
        elif srpm_url:
            chroot_status = StatusEnum("waiting")
            source_status = StatusEnum("importing")
        else:
            chroot_status = StatusEnum("waiting")
            source_status = StatusEnum("pending")

        build = models.Build(
            user=user,
            pkgs=pkgs,
            copr=copr,
            repos=repos,
            source_type=source_type,
            source_json=source_json,
            source_status=source_status,
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

        for chroot in chroots:
            git_hash = None
            if git_hashes:
                git_hash = git_hashes.get(chroot.name)
            buildchroot = models.BuildChroot(
                build=build,
                status=chroot_status,
                mock_chroot=chroot,
                git_hash=git_hash,
            )
            db.session.add(buildchroot)

        return build

    @classmethod
    def rebuild_package(cls, package, source_dict_update={}, copr_dir=None, update_callback=None,
                        scm_object_type=None, scm_object_id=None, scm_object_url=None):

        source_dict = package.source_json_dict
        source_dict.update(source_dict_update)
        source_json = json.dumps(source_dict)

        if not copr_dir:
            copr_dir = package.copr.main_dir

        build = models.Build(
            user=None,
            pkgs=None,
            package=package,
            copr=package.copr,
            repos=package.copr.repos,
            source_status=StatusEnum("pending"),
            source_type=package.source_type,
            source_json=source_json,
            submitted_on=int(time.time()),
            enable_net=package.copr.build_enable_net,
            timeout=DEFAULT_BUILD_TIMEOUT,
            copr_dir=copr_dir,
            update_callback=update_callback,
            scm_object_type=scm_object_type,
            scm_object_id=scm_object_id,
            scm_object_url=scm_object_url,
        )
        db.session.add(build)

        chroots = package.copr.active_chroots
        status = StatusEnum("waiting")
        for chroot in chroots:
            buildchroot = models.BuildChroot(
                build=build,
                status=status,
                mock_chroot=chroot,
                git_hash=None
            )
            db.session.add(buildchroot)

        cls.process_update_callback(build)
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
                 "started_on": 1390866440
               },
               {
                 "id": 2,
                 "copr_id": 1,
                 "status": 0,
                 "chroot": "fedora-18-x86_64",
                 "result_dir": "baz",
                 "ended_on": 1390866440
               }]
            }
        """
        log.info("Updating build {} by: {}".format(build.id, upd_dict))

        # update build
        for attr in ["built_packages", "srpm_url"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(build, attr, value)

        # update source build status
        if upd_dict.get("task_id") == build.task_id:
            build.result_dir = upd_dict.get("result_dir", "")

            if upd_dict.get("status") == StatusEnum("succeeded"):
                new_status = StatusEnum("importing")
            else:
                new_status = upd_dict.get("status")

            build.source_status = new_status
            if new_status == StatusEnum("failed") or \
                   new_status == StatusEnum("skipped"):
                for ch in build.build_chroots:
                    ch.status = new_status
                    ch.ended_on = upd_dict.get("ended_on") or time.time()
                    db.session.add(ch)

            if new_status == StatusEnum("failed"):
                build.fail_type = FailTypeEnum("srpm_build_error")

            cls.process_update_callback(build)
            db.session.add(build)
            return

        if "chroot" in upd_dict:
            # update respective chroot status
            for build_chroot in build.build_chroots:
                if build_chroot.name == upd_dict["chroot"]:
                    build_chroot.result_dir = upd_dict.get("result_dir", "")

                    if "status" in upd_dict and build_chroot.status not in BuildsLogic.terminal_states:
                        build_chroot.status = upd_dict["status"]

                    if upd_dict.get("status") in BuildsLogic.terminal_states:
                        build_chroot.ended_on = upd_dict.get("ended_on") or time.time()

                    if upd_dict.get("status") == StatusEnum("starting"):
                        build_chroot.started_on = upd_dict.get("started_on") or time.time()

                    db.session.add(build_chroot)

                    # If the last package of a module was successfully built,
                    # then send an action to create module repodata on backend
                    if (build.module
                            and upd_dict.get("status") == StatusEnum("succeeded")
                            and all(b.status == StatusEnum("succeeded") for b in build.module.builds)):
                        ActionsLogic.send_build_module(build.copr, build.module)

        cls.process_update_callback(build)
        db.session.add(build)

    @classmethod
    def process_update_callback(cls, build):
        parsed_git_url = helpers.get_parsed_git_url(build.copr.scm_repo_url)
        if not parsed_git_url:
            return

        if build.update_callback == 'pagure_flag_pull_request':
            api_url = 'https://{0}/api/0/{1}/pull-request/{2}/flag'.format(
                parsed_git_url.netloc, parsed_git_url.path, build.scm_object_id)
            return cls.pagure_flag(build, api_url)

        elif build.update_callback == 'pagure_flag_commit':
            api_url = 'https://{0}/api/0/{1}/c/{2}/flag'.format(
                parsed_git_url.netloc, parsed_git_url.path, build.scm_object_id)
            return cls.pagure_flag(build, api_url)

    @classmethod
    def pagure_flag(cls, build, api_url):
        headers = {
            'Authorization': 'token {}'.format(build.copr.scm_api_auth.get('api_key'))
        }

        if build.srpm_url:
            progress = 50
        else:
            progress = 10

        state_table = {
            'failed': ('failure', 0),
            'succeeded': ('success', 100),
            'canceled': ('canceled', 0),
            'running': ('pending', progress),
            'pending': ('pending', progress),
            'skipped': ('error', 0),
            'starting': ('pending', progress),
            'importing': ('pending', progress),
            'forked': ('error', 0),
            'waiting': ('pending', progress),
            'unknown': ('error', 0),
        }

        build_url = os.path.join(
            app.config['PUBLIC_COPR_BASE_URL'],
            'coprs', build.copr.full_name.replace('@', 'g/'),
            'build', str(build.id)
        )

        data = {
            'username': 'Copr build',
            'comment': '#{}'.format(build.id),
            'url': build_url,
            'status': state_table[build.state][0],
            'percent': state_table[build.state][1],
            'uid': str(build.id),
        }

        log.info('Sending data to Pagure API: %s', pprint.pformat(data))
        response = requests.post(api_url, data=data, headers=headers)
        log.info('Pagure API response: %s', response.text)

    @classmethod
    def cancel_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise exceptions.InsufficientRightsException(
                "You are not allowed to cancel this build.")
        if not build.cancelable:
            if build.status == StatusEnum("starting"):
                # this is not intuitive, that's why we provide more specific message
                err_msg = "Cannot cancel build {} in state 'starting'".format(build.id)
            else:
                err_msg = "Cannot cancel build {}".format(build.id)
            raise exceptions.RequestCannotBeExecuted(err_msg)

        if build.status == StatusEnum("running"): # otherwise the build is just in frontend
            ActionsLogic.send_cancel_build(build)

        build.canceled = True
        cls.process_update_callback(build)

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
        chroots = filter(lambda x: x.status != StatusEnum("succeeded"), build.build_chroots)
        for chroot in chroots:
            chroot.status = StatusEnum("failed")
        cls.process_update_callback(build)
        return build

    @classmethod
    def last_modified(cls, copr):
        """ Get build datetime (as epoch) of last successful build

        :arg copr: object of copr
        """
        builds = cls.get_multiple_by_copr(copr)

        last_build = (
            builds.join(models.BuildChroot)
            .filter((models.BuildChroot.status == StatusEnum("succeeded"))
                    | (models.BuildChroot.status == StatusEnum("skipped")))
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

    @classmethod
    def filter_by_package_name(cls, query, package_name):
        return query.join(models.Package).filter(models.Package.name == package_name)


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
