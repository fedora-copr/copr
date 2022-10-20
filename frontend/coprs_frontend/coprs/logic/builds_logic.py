import tempfile
import shutil
import json
import os
import pprint
import time
import requests

from sqlalchemy.sql import text
from sqlalchemy.sql.expression import not_
from sqlalchemy.orm import joinedload, selectinload, load_only, contains_eager
from sqlalchemy import func, desc, or_, and_
from sqlalchemy.sql import false,true
from werkzeug.utils import secure_filename
from sqlalchemy import bindparam, Integer, String
from sqlalchemy.exc import IntegrityError

from copr_common.enums import FailTypeEnum, StatusEnum
from coprs import app
from coprs import cache
from coprs import db
from coprs import models
from coprs import helpers
from coprs.request import save_form_file_field_to
from coprs.exceptions import (
    ActionInProgressException,
    BadRequest,
    ConflictingRequest,
    DuplicateException,
    InsufficientRightsException,
    InsufficientStorage,
    MalformedArgumentException,
    UnrepeatableBuildException,
)

from coprs.logic import coprs_logic
from coprs.logic import users_logic
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.dist_git_logic import DistGitLogic
from coprs.models import BuildChroot
from coprs.logic.coprs_logic import MockChrootsLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.batches_logic import BatchesLogic
from coprs.measure import checkpoint

from .helpers import get_graph_parameters
log = app.logger


PROCESSING_STATES = [StatusEnum(s) for s in [
    "running", "pending", "starting", "importing", "waiting",
]]


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
        """ Returns source build tasks with given status. If background is
            specified then returns normal jobs (false) or background jobs (true)
        """
        result = models.Build.query\
            .filter(models.Build.source_status == status)\
            .order_by(models.Build.id.asc())
        if background is not None:
            result = result.filter(models.Build.is_background == (true() if background else false()))
        return result

    @classmethod
    @cache.memoize(timeout=2*60)
    def get_recent_task_ids(cls, user=None, limit=100, period_days=2):
        query_args = (
            models.BuildChroot.build_id,
            func.max(models.BuildChroot.ended_on).label('max_ended_on'),
            models.Build.submitted_on,
        )
        group_by_args = (
            models.BuildChroot.build_id,
            models.Build.submitted_on,
        )


        if user:
            query_args += (models.Build.user_id,)
            group_by_args += (models.Build.user_id,)

        subquery = (db.session.query(*query_args)
            .join(models.Build)
            .group_by(*group_by_args)
            .having(func.count() == func.count(models.BuildChroot.ended_on))
            .having(models.Build.submitted_on > time.time() - 3600*24*period_days)
        )
        if user:
            subquery = subquery.having(models.Build.user_id == user.id)

        subquery = subquery.order_by(desc('max_ended_on')).limit(limit).subquery()

        query = models.Build.query.join(subquery, subquery.c.build_id == models.Build.id)
        return [i.id for i in query.all()]

    @classmethod
    def get_recent_tasks(cls, *args, **kwargs):
        task_ids = cls.get_recent_task_ids(*args, **kwargs)
        query = models.Build.query.filter(models.Build.id.in_(task_ids))
        return sorted(query.all(), key=lambda o: task_ids.index(o.id))

    @classmethod
    def get_running_tasks_by_time(cls, start, end):
        result = models.BuildChroot.query\
            .filter(models.BuildChroot.ended_on > start)\
            .filter(models.BuildChroot.started_on < end)\
            .order_by(models.BuildChroot.started_on.asc())

        return result

    @classmethod
    def get_chroot_histogram(cls, start, end):
        chroots = []
        chroot_query = BuildChroot.query\
            .filter(models.BuildChroot.started_on < end)\
            .filter(models.BuildChroot.ended_on > start)\
            .with_entities(BuildChroot.mock_chroot_id,
                           func.count(BuildChroot.mock_chroot_id))\
            .group_by(BuildChroot.mock_chroot_id)\
            .order_by(func.count(BuildChroot.mock_chroot_id).desc())

        for chroot in chroot_query:
            chroots.append([chroot[0], chroot[1]])

        mock_chroots = coprs_logic.MockChrootsLogic.get_multiple()
        for mock_chroot in mock_chroots:
            for l in chroots:
                if l[0] == mock_chroot.id:
                    l[0] = mock_chroot.name
        return chroots

    @classmethod
    def get_pending_jobs_bucket(cls, start, end):
        query = text("""
            SELECT COUNT(*) as result
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

        res = db.engine.execute(query, start=start, end=end, status=StatusEnum("pending"))
        return res.first().result

    @classmethod
    def get_running_jobs_bucket(cls, start, end):
        query = text("""
            SELECT COUNT(*) as result
            FROM build_chroot
            WHERE
                started_on < :end
                AND (ended_on > :start OR (ended_on is NULL AND status = :status))
                -- for currently running builds we need to filter on status=running because there might be failed
                -- builds that have ended_on=NULL
        """)

        res = db.engine.execute(query, start=start, end=end, status=StatusEnum("running"))
        return res.first().result

    @classmethod
    def get_cached_graph_data(cls, params):
        data = {
            "pending": [],
            "running": [],
        }
        result = models.BuildsStatistics.query\
            .filter(models.BuildsStatistics.stat_type == params["type"])\
            .filter(models.BuildsStatistics.time >= params["start"])\
            .filter(models.BuildsStatistics.time <= params["end"])\
            .order_by(models.BuildsStatistics.time)

        for row in result:
            data["pending"].append(row.pending)
            data["running"].append(row.running)

        return data

    @classmethod
    def get_task_graph_data(cls, type):
        data = [["pending"], ["running"], ["avg running"], ["time"]]
        params = get_graph_parameters(type)
        cached_data = cls.get_cached_graph_data(params)
        data[0].extend(cached_data["pending"])
        data[1].extend(cached_data["running"])

        for i in range(len(data[0]) - 1, params["steps"]):
            step_start = params["start"] + i * params["step"]
            step_end = step_start + params["step"]
            pending = cls.get_pending_jobs_bucket(step_start, step_end)
            running = cls.get_running_jobs_bucket(step_start, step_end)
            data[0].append(pending)
            data[1].append(running)
            cls.cache_graph_data(type, time=step_start, pending=pending, running=running)

        running_total = 0
        for i in range(1, params["steps"] + 1):
            running_total += data[1][i]

        data[2].extend([running_total * 1.0 / params["steps"]] * (len(data[0]) - 1))

        for i in range(params["start"], params["end"], params["step"]):
            data[3].append(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(i)))

        return data

    @classmethod
    def get_small_graph_data(cls, type):
        data = [[""]]
        params = get_graph_parameters(type)
        cached_data = cls.get_cached_graph_data(params)
        data[0].extend(cached_data["running"])

        for i in range(len(data[0]) - 1, params["steps"]):
            step_start = params["start"] + i * params["step"]
            step_end = step_start + params["step"]
            running = cls.get_running_jobs_bucket(step_start, step_end)
            data[0].append(running)
            cls.cache_graph_data(type, time=step_start, running=running)

        return data

    @classmethod
    def cache_graph_data(cls, type, time, pending=0, running=0):
        result = models.BuildsStatistics.query\
                .filter(models.BuildsStatistics.stat_type == type)\
                .filter(models.BuildsStatistics.time == time).first()
        if result:
            return

        try:
            cached_data = models.BuildsStatistics(
                time = time,
                stat_type = type,
                running = running,
                pending = pending
            )
            db.session.add(cached_data)
            db.session.commit()
        except IntegrityError: # other process already calculated the graph data and cached it
            db.session.rollback()

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
    def _todo_states(cls, data_type):
        """
        When data_type is not "for_backend", we only return builds which are in
        "pending" state.  That queries are used by the Frontend Web-UI/API and
        that's what is the end-user interested in when looking at pending tasks.

        From the Backend perspective though, "starting" and "running" tasks are
        pending, too - because if something fails (e.g. backend VM restart,
        which kills the BackgroundWorker processes) we have to "re-process" such
        tasks too (otherwise they stay in starting/running states forever).
        """
        todo_states = ["pending"]
        if data_type == "for_backend":
            todo_states += ["starting", "running"]
        return [StatusEnum(x) for x in todo_states]

    @classmethod
    def get_pending_srpm_build_tasks(cls, background=None, data_type=None):
        query = (
            models.Build.query
            .join(models.Copr)
            .filter(models.Build.canceled == false())
            .filter(models.Build.source_status.in_(cls._todo_states(data_type)))
            .order_by(models.Build.is_background.asc(), models.Build.id.asc())
        )

        if data_type in ["for_backend", "overview"]:

            load_build_fields = ["is_background", "submitted_by", "batch_id",
                                 "user_id"]
            if data_type == "for_backend":
                # The custom method allows us to set the chroot for SRPM builds
                load_build_fields += ["source_type", "source_json"]

            query = query.options(
                load_only(*load_build_fields),
                # from copr project info we only need the project name
                joinedload('copr').load_only("user_id", "group_id", "name")
                .options(
                    joinedload('user').load_only("username"),
                    joinedload("group").load_only("name")
                ),
                # submitter
                joinedload('user').load_only("username"),
                # preload also batch info
                joinedload('batch').load_only("blocked_by_id"),
            )
        if background is not None:
            query = query.filter(models.Build.is_background == (true() if background else false()))
        return query

    @classmethod
    def get_pending_build_tasks(cls, background=None, data_type=None):
        """
        Get list of BuildChroot objects that are to be (re)processed.
        """

        query = (
            models.BuildChroot.query
            .join(models.Build)
            .join(models.CoprDir)
        )

        # We need the Package information for the /get-pending-srpm-task/ and
        # /get-build-task/ routes, but anywhere else.
        if data_type is None:
            # TODO: BuildChroot objects should be self-standing.  The thing is
            # that this is racy -- Package reference provides some build
            # configuration which can be changed in the middle of the
            # BuildChroot processing.
            query = query.join(models.Package, models.Package.id == models.Build.package_id)

        query = (
            query.filter(models.Build.canceled == false())
            .filter(models.BuildChroot.status.in_(cls._todo_states(data_type)))
            .order_by(models.Build.is_background.asc(), models.Build.id.asc()))

        if data_type in ["for_backend", "overview"]:
            query = query.options(
                load_only("build_id"),
                joinedload('build').load_only("id", "is_background", "submitted_by", "batch_id")
                .options(
                    # from copr project info we only need the project name
                    joinedload('copr').load_only("user_id", "group_id", "name")
                    .options(
                        joinedload('user').load_only("username"),
                        joinedload("group").load_only("name")
                    ),
                    # submitter
                    joinedload('user').load_only("username"),
                    # preload also batch info
                    joinedload('batch').load_only("blocked_by_id"),
                ),
                joinedload('mock_chroot').load_only("os_version", "os_release", "arch", "tags_raw"),
            )

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
    def get_copr_builds_list(cls, copr, dirname=None):
        query = models.Build.query.filter(models.Build.copr_id==copr.id)
        if dirname:
            copr_dir = coprs_logic.CoprDirsLogic.get_by_copr(copr, dirname)
            query = query.filter(models.Build.copr_dir_id==copr_dir.id)
        query = query.options(selectinload('build_chroots'), selectinload('package'))
        return query

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
                               srpm_url=source_build.srpm_url, copr_dirname=source_build.copr_dir.name, **build_options)
        build.package_id = source_build.package_id
        build.pkg_version = source_build.pkg_version
        build.resubmitted_from_id = source_build.id

        return build

    @classmethod
    def create_new_from_url(cls, user, copr, url, chroot_names=None,
                            copr_dirname=None, **build_options):
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
                              pkgs=url, srpm_url=srpm_url, copr_dirname=copr_dirname, **build_options)

    @classmethod
    def create_new_from_scm(cls, user, copr, scm_type, clone_url,
                            committish='', subdirectory='', spec='', srpm_build_method='rpkg',
                            chroot_names=None, copr_dirname=None, **build_options):
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
        return cls.create_new(user, copr, source_type, source_json, chroot_names, copr_dirname=copr_dirname, **build_options)

    @classmethod
    def create_new_from_pypi(cls, user, copr, pypi_package_name,
                             pypi_package_version, spec_generator,
                             spec_template, python_versions, chroot_names=None,
                             copr_dirname=None, **build_options):
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
                                  "spec_generator": spec_generator,
                                  "spec_template": spec_template,
                                  "python_versions": python_versions})
        return cls.create_new(user, copr, source_type, source_json, chroot_names, copr_dirname=copr_dirname, **build_options)

    @classmethod
    def create_new_from_rubygems(cls, user, copr, gem_name, chroot_names=None,
                                 copr_dirname=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :type gem_name: str
        :type chroot_names: List[str]
        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("rubygems")
        source_json = json.dumps({"gem_name": gem_name})
        return cls.create_new(user, copr, source_type, source_json, chroot_names, copr_dirname=copr_dirname, **build_options)

    @classmethod
    def create_new_from_custom(cls, user, copr, script, script_chroot=None, script_builddeps=None,
                               script_resultdir=None, script_repos=None, chroot_names=None,
                               copr_dirname=None, **kwargs):
        """
        :type user: models.User
        :type copr: models.Copr
        :type script: str
        :type script_chroot: str
        :type script_builddeps: str
        :type script_resultdir: str
        :type script_repos: str
        :type chroot_names: List[str]
        :rtype: models.Build
        """
        source_type = helpers.BuildSourceEnum("custom")
        source_dict = {
            'script': script,
            'chroot': script_chroot,
            'builddeps': script_builddeps,
            'resultdir': script_resultdir,
            'repos': script_repos,
        }

        return cls.create_new(user, copr, source_type, json.dumps(source_dict),
                              chroot_names, copr_dirname=copr_dirname, **kwargs)

    @classmethod
    def create_new_from_distgit(cls, user, copr, package_name,
                                distgit_name=None, distgit_namespace=None,
                                committish=None, chroot_names=None,
                                copr_dirname=None, **build_options):
        """ Request build of package from DistGit repository """
        source_type = helpers.BuildSourceEnum("distgit")

        source_dict = {}

        if "clone_url" in build_options:
            # Even though the DistGit instance is (probably) chosen, use a
            # different clone URL.  If the pattern for this URL isn't configured
            # on the builder side, the build may fail.
            source_dict["clone_url"] = build_options["clone_url"]
        else:
            source_dict["clone_url"] = DistGitLogic.get_clone_url(
                    distgit_name, package_name, distgit_namespace)

        if committish:
            source_dict["committish"] = committish

        return cls.create_new(
            user, copr, source_type, json.dumps(source_dict), chroot_names,
            copr_dirname=copr_dirname, **build_options)

    @classmethod
    def create_new_from_upload(cls, user, copr, form_field, orig_filename,
                               chroot_names=None, copr_dirname=None, **build_options):
        """
        :type user: models.User
        :type copr: models.Copr
        :param form_field: object representing an uploaded file in form
        :return:
        """
        tmp = None
        try:
            tmp = tempfile.mkdtemp(dir=app.config["STORAGE_DIR"])
            tmp_name = os.path.basename(tmp)
            filename = secure_filename(orig_filename)
            file_path = os.path.join(tmp, filename)
            save_form_file_field_to(form_field, file_path)
        except OSError as error:
            if tmp:
                shutil.rmtree(tmp)
            raise InsufficientStorage("Can not create storage directory for uploaded file: {}".format(str(error)))

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
                                   chroot_names, pkgs=pkg_url, srpm_url=srpm_url,
                                   copr_dirname=copr_dirname, **build_options)
        except Exception:
            shutil.rmtree(tmp)  # todo: maybe we should delete in some cleanup procedure?
            raise

        return build

    @classmethod
    def create_new(cls, user, copr, source_type, source_json, chroot_names=None, pkgs="",
                   git_hashes=None, skip_import=False, background=False, batch=None,
                   srpm_url=None, copr_dirname=None, package=None,
                   package_chroots_subset=None, **build_options):
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
        if not copr.active_copr_chroots:
            raise BadRequest("Can't create build - project {} has no active chroots".format(copr.full_name))

        # If no chroots are specified by the user, we can submit the build
        # without any build_chroots. Once the SRPM build is finished and backend
        # requests update of its state in the databse, build chroots are
        # generated
        chroots = []

        if copr.fedora_review:
            source_json = json.loads(source_json)
            source_json["fedora_review"] = True
            source_json = json.dumps(source_json)

        # If chroots are specified by the user, we should create the build only
        # for them
        if chroot_names:
            for chroot in copr.active_chroots:
                if chroot.name in chroot_names:
                    chroots.append(chroot)

        # If we skip the importing phase (i.e. set SRPM build status directly to
        # "succeeded"), there is no update from backend and therefore we would
        # end up with no build_chroots at all. Let's generate them now
        elif skip_import and srpm_url:
            for chroot in copr.active_chroots:
                chroots.append(chroot)

        build = cls.add(
            user=user,
            package=package,
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
            copr_dirname=copr_dirname,
            bootstrap=build_options.get("bootstrap"),
            isolation=build_options.get("isolation"),
            after_build_id=build_options.get("after_build_id"),
            with_build_id=build_options.get("with_build_id"),
            package_chroots_subset=package_chroots_subset,
            packit_forge_project=build_options.get("packit_forge_project"),
        )

        if "timeout" in build_options:
            build.timeout = build_options["timeout"]

        return build

    @classmethod
    def _setup_batch(cls, batch, after_build_id, with_build_id, user):
        # those three are exclusive!
        if sum([bool(x) for x in
                [batch, with_build_id, after_build_id]]) > 1:
            raise BadRequest("Multiple build batch specifiers")

        if with_build_id:
            batch = BatchesLogic.get_batch_or_create(with_build_id, user, True)

        if after_build_id:
            old_batch = BatchesLogic.get_batch_or_create(after_build_id, user)
            batch = models.Batch()
            batch.blocked_by = old_batch
            db.session.add(batch)

        return batch

    @classmethod
    def assign_buildchroots(cls, build, chroot_names, status=None,
                            git_hashes=None, **kwargs):
        """
        For each chroot_name allocate a new BuildChroot instance and assign it
        to the build.
        """
        something_added = False
        for chroot in chroot_names:
            something_added = True
            additional_args = {}
            if git_hashes:
                additional_args["git_hash"] = git_hashes.get(chroot.name)
            if status is None:
                status = StatusEnum("waiting")
            buildchroot = BuildChrootsLogic.new(
                build=build,
                mock_chroot=chroot,
                status=status,
                **kwargs,
                **additional_args,
            )
            db.session.add(buildchroot)
        return something_added

    @classmethod
    def assign_buildchroots_from_package(cls, build, **kwargs):
        """
        If build has already assigned build.package, create and assign new set
        of BuildChroot instances according to 'build.package.chroots'.  This
        e.g. respects the Copr.chroot_denylist config.
        """
        if not build.package:
            return False
        return cls.assign_buildchroots(
            build,
            build.package.chroots,
            **kwargs,
        )

    @staticmethod
    def _chroots_to_add(package, chroots, package_chroots_subset):
        """
        Get the list of chroot names to be assigned to build.
        """
        if package:
            if not chroots:
                chroots = package.chroots
            if package_chroots_subset:
                chroots = list(set(chroots).intersection(set(package.chroots)))

            # When we know the package we build already, there's no reason to
            # delay BuildChroot allocation at this point in time.  So the chroot
            # list must be set, and non-empty.
            if not chroots:
                raise MalformedArgumentException(
                    "No chroots selected (or automatically selectable) for "
                    "the package \"%s\" in \"%s\""
                    % (package.name, package.copr.name))

        elif chroots is None:
            # when package is unknown, we assign the chroots later when the
            # source build is done (and thus also the package name is known).
            chroots = []

        return chroots

    @classmethod
    def add(cls, user, pkgs, copr, source_type=None, source_json=None,
            repos=None, chroots=None, timeout=None, enable_net=True,
            git_hashes=None, skip_import=False, background=False, batch=None,
            srpm_url=None, copr_dirname=None, bootstrap=None, isolation=None,
            package=None, after_build_id=None, with_build_id=None,
            package_chroots_subset=None, packit_forge_project=None):

        coprs_logic.CoprsLogic.raise_if_unfinished_blocking_action(
            copr, "Can't build while there is an operation in progress: {action}")
        coprs_logic.CoprsLogic.raise_if_packit_forge_project_cant_build_in_copr(copr, packit_forge_project)
        users_logic.UsersLogic.raise_if_cant_build_in_copr(
            user, copr,
            "You don't have permissions to build in this copr.")

        batch = cls._setup_batch(batch, after_build_id, with_build_id, user)

        if not repos:
            repos = copr.repos

        # todo: eliminate pkgs and this check
        if pkgs and (" " in pkgs or "\n" in pkgs or "\t" in pkgs or pkgs.strip() != pkgs):
            raise MalformedArgumentException("Trying to create a build using src_pkg "
                                                        "with bad characters. Forgot to split?")

        # just temporary to keep compatibility
        if not source_type or not source_json:
            source_type = helpers.BuildSourceEnum("link")
            source_json = json.dumps({"url":pkgs})

        if skip_import and srpm_url:
            chroot_status = StatusEnum("pending")
            source_status = StatusEnum("succeeded")
        else:
            chroot_status = StatusEnum("waiting")
            source_status = StatusEnum("pending")

        copr_dir = None
        if copr_dirname:
            copr_dir = coprs_logic.CoprDirsLogic.get_or_create(copr, copr_dirname)

        chroots = cls._chroots_to_add(package, chroots, package_chroots_subset)

        build = models.Build(
            user=user,
            package=package,
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
            copr_dir=copr_dir,
            bootstrap=bootstrap,
            isolation=isolation,
        )

        if timeout:
            build.timeout = timeout or app.config["DEFAULT_BUILD_TIMEOUT"]

        db.session.add(build)
        cls.assign_buildchroots(
            build,
            chroots,
            git_hashes=git_hashes,
            status=chroot_status,
        )
        return build

    @classmethod
    def rebuild_package(cls, package, source_dict_update={}, copr_dir=None, update_callback=None,
                        scm_object_type=None, scm_object_id=None,
                        scm_object_url=None, submitted_by=None):
        """
        Rebuild a concrete package by a webhook.  This is different from
        create_new() because we don't have a concrete 'user' who submits this
        (only submitted_by string).
        """

        source_dict = package.source_json_dict
        source_dict.update(source_dict_update)
        source_json = json.dumps(source_dict)

        if not copr_dir:
            copr_dir = package.copr.main_dir

        # TODO: Callers do not expect us to raise exceptions here.  It would be
        # ideal to return None, but callers don't expect None return value
        # either.
        assert bool(package.copr.active_copr_chroots)

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
            timeout=app.config["DEFAULT_BUILD_TIMEOUT"],
            copr_dir=copr_dir,
            update_callback=update_callback,
            scm_object_type=scm_object_type,
            scm_object_id=scm_object_id,
            scm_object_url=scm_object_url,
            submitted_by=submitted_by,
            is_background=True,
        )
        db.session.add(build)
        cls.assign_buildchroots_from_package(build)
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
            except OSError:
                log.exception("Can't remove tmpdir '%s'", tmp)


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

        pkg_name = upd_dict.get('pkg_name', None)
        if not build.package and pkg_name:
            # assign the package if it isn't already
            if not PackagesLogic.get(build.copr.id, pkg_name).first():
                # create the package if it doesn't exist
                try:
                    package = PackagesLogic.add(
                        build.copr.user, build.copr,
                        pkg_name, build.source_type, build.source_json)
                    db.session.add(package)
                    db.session.commit()
                except (IntegrityError, DuplicateException) as e:
                    app.logger.exception(e)
                    db.session.rollback()
                    return
            build.package = PackagesLogic.get(build.copr.id, pkg_name).first()

        for attr in ["built_packages", "srpm_url", "pkg_version"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(build, attr, value)

        # update source build status
        if str(upd_dict.get("task_id")) == str(build.task_id):
            build.result_dir = upd_dict.get("result_dir", "")

            new_status = upd_dict.get("status")
            if new_status == StatusEnum("succeeded"):
                new_status = StatusEnum("importing")
                chroot_status=StatusEnum("waiting")
                if not build.build_chroots:
                    # When BuildChroots are not yet allocated, allocate them now
                    # from the assigned Package setting.
                    if not cls.assign_buildchroots_from_package(
                            build, status=chroot_status, git_hash=None):
                        new_status = StatusEnum("failed")
                else:
                    for buildchroot in build.build_chroots:
                        buildchroot.status = chroot_status
                        db.session.add(buildchroot)

            build.source_status = new_status
            if new_status == StatusEnum("failed") or \
                   new_status == StatusEnum("skipped"):
                for ch in build.build_chroots:
                    ch.status = new_status
                    ch.ended_on = upd_dict.get("ended_on") or time.time()
                    ch.started_on = upd_dict.get("started_on", ch.ended_on)
                    db.session.add(ch)

            if new_status == StatusEnum("failed"):
                build.fail_type = FailTypeEnum("srpm_build_error")
                BuildsLogic.delete_local_source(build)

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
                        assert isinstance(upd_dict, dict)
                        BuildChrootResultsLogic.create_from_dict(
                            build_chroot, upd_dict.get("results"))

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

        username = "Copr build"
        if build.package:
            username += " - " + build.package.name

        data = {
            'username': username,
            'comment': '#{}'.format(build.id),
            'url': build_url,
            'status': state_table[build.state][0],
            'percent': state_table[build.state][1],
            'uid': str(build.id),
        }

        log.debug('Sending data to Pagure API: %s', pprint.pformat(data))
        response = requests.post(api_url, data=data, headers=headers)
        log.debug('Pagure API response: %s', response.text)

    @classmethod
    def cancel_build(cls, user, build):
        if not user.can_build_in(build.copr):
            raise InsufficientRightsException(
                "You are not allowed to cancel this build.")
        if not build.cancelable:
            err_msg = "Cannot cancel build {}".format(build.id)
            raise ConflictingRequest(err_msg)

        # No matter the state, we tell backend to cancel this build.  Even when
        # the build is in pending state (worker manager may be already handling
        # this build ATM, and creating an asynchronous worker which needs to be
        # canceled).
        ActionsLogic.send_cancel_build(build)

        build.canceled = True
        cls.process_update_callback(build)


    @classmethod
    def check_build_to_delete(cls, user, build):
        """
        :type user: models.User
        :type build: models.Build
        """
        if not user.can_edit(build.copr) or build.persistent:
            raise InsufficientRightsException(
                "You are not allowed to delete build `{}`.".format(build.id))

        if not build.finished:
            raise ActionInProgressException(
                "You can not delete build `{}` which is not finished.".format(build.id),
                "Unfinished build")

    @classmethod
    def delete_build(cls, user, build, send_delete_action=True):
        """
        :type user: models.User
        :type build: models.Build
        """
        cls.check_build_to_delete(user, build)

        if send_delete_action:
            ActionsLogic.send_delete_build(build)

        db.session.delete(build)

    @classmethod
    def delete_builds(cls, user, build_ids):
        """
        Delete builds specified by list of IDs

        :type user: models.User
        :type build_ids: list of Int
        """
        to_delete = []
        no_permission = []
        still_running = []

        build_ids = set(build_ids)
        builds = cls.get_by_ids(build_ids)
        for build in builds:
            try:
                cls.check_build_to_delete(user, build)
                to_delete.append(build)
            except InsufficientRightsException:
                no_permission.append(build.id)
            except ActionInProgressException:
                still_running.append(build.id)
            finally:
                build_ids.remove(build.id)

        if build_ids or no_permission or still_running:
            msg = ""
            if no_permission:
                msg += "You don't have permissions to delete build(s) {0}.\n"\
                    .format(", ".join(map(str, no_permission)))
            if still_running:
                msg += "Build(s) {0} are still running.\n"\
                    .format(", ".join(map(str, still_running)))
            if build_ids:
                msg += "Build(s) {0} don't exist.\n"\
                    .format(", ".join(map(str, build_ids)))

            raise BadRequest(msg)

        if to_delete:
            ActionsLogic.send_delete_multiple_builds(to_delete)

        for build in to_delete:
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
        if build.source_status != StatusEnum("succeeded"):
            build.source_status = StatusEnum("failed")
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

    @classmethod
    def clean_old_builds(cls):
        dirs = (
            db.session.query(
                models.CoprDir.id,
                models.Package.id,
                models.Package.max_builds)
            .join(models.Build, models.Build.copr_dir_id==models.CoprDir.id)
            .join(models.Package)
            .filter(models.Package.max_builds > 0)
            .group_by(
                models.CoprDir.id,
                models.Package.max_builds,
                models.Package.id)
            .having(func.count(models.Build.id) > models.Package.max_builds)
        )

        for dir_id, package_id, limit in dirs.all():
            delete_builds = (
                models.Build.query.filter(
                    models.Build.copr_dir_id==dir_id,
                    models.Build.package_id==package_id)
                .order_by(desc(models.Build.id))
                .offset(limit)
                .all()
            )

            for build in delete_builds:
                try:
                    cls.delete_build(build.copr.user, build)
                except ActionInProgressException:
                    # postpone this one to next day run
                    log.error("Build(id={}) delete failed, unfinished action.".format(build.id))

    @classmethod
    def delete_orphaned_builds(cls):
        builds_to_delete = models.Build.query\
            .join(models.Copr, models.Build.copr_id == models.Copr.id)\
            .filter(models.Copr.deleted == True)

        counter = 0
        for build in builds_to_delete:
            cls.delete_build(build.copr.user, build)
            counter += 1
            if counter >= 100:
                db.session.commit()
                counter = 0

        if counter > 0:
            db.session.commit()

    @classmethod
    def processing_builds(cls):
        """
        Query for all the builds which are not yet finished, it means all the
        builds that have non-finished source status, or any non-finished
        existing build chroot.
        """
        build_ids_with_bch = db.session.query(BuildChroot.build_id).filter(
            BuildChroot.status.in_(PROCESSING_STATES),
        )
        # skip waiting state, we need to fix issue #1539
        source_states = set(PROCESSING_STATES)-{StatusEnum("waiting")}
        return models.Build.query.filter(and_(
            not_(models.Build.canceled),
            or_(
                models.Build.id.in_(build_ids_with_bch),
                models.Build.source_status.in_(source_states),
            ),
        ))


class BuildChrootsLogic(object):
    @classmethod
    def new(cls, build, mock_chroot, **kwargs):
        """
        Create new instance of BuildChroot
        (which is not assigned to any session)

        Each freshly created instance of BuildChroot has to be assigned to
        pre-existing Build and MockChroot, hence the mandatory arguments.
        """
        copr_chroot = coprs_logic.CoprChrootsLogic.get_by_mock_chroot_id(
            build.copr, mock_chroot.id
        ).one()
        return models.BuildChroot(
            mock_chroot=mock_chroot,
            copr_chroot=copr_chroot,
            build=build,
            **kwargs,
        )

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
    def filter_by_group_name(cls, query, group_name):
        return query.filter(models.Group.name == group_name)

    @classmethod
    def filter_by_copr_and_mock_chroot(cls, query, copr, mock_chroot):
        """
        Filter BuildChroot query so it returns only instances related to
        particular Copr and MockChroot.
        """
        return (
            query.join(models.BuildChroot.build)
            .filter(models.BuildChroot.mock_chroot_id == mock_chroot.id)
            .filter(models.Build.copr_id == copr.id)
        )

    @classmethod
    def by_copr_and_mock_chroot(cls, copr, mock_chroot):
        """
        Given Copr and MockChroot instances, return query object which provides
        a list of related BuildChroots.
        """
        return cls.filter_by_copr_and_mock_chroot(BuildChroot.query, copr,
                                                  mock_chroot)

class BuildChrootResultsLogic:
    """
    High-level interface for working with `models.BuildChrootResult` objects
    """

    @classmethod
    def create(cls, build_chroot, name, epoch, version, release, arch):
        """
        Create a new record about a built package in some `BuildChroot`
        """
        return models.BuildChrootResult(
            build_chroot_id=build_chroot,
            build_chroot=build_chroot,
            name=name,
            epoch=epoch,
            version=version,
            release=release,
            arch=arch,
        )


    @classmethod
    def create_from_dict(cls, build_chroot, results):
        """
        Parses a `dict` in the following format

            {"packages": [{"name": "foo", "epoch": 0, ...}]}

        and records all of the built packages for a given `BuildChroot`.
        """
        if results is None or "packages" not in results:
            return []
        return [cls.create(build_chroot, **result)
                for result in results["packages"]]


class BuildsMonitorLogic(object):
    @classmethod
    def package_build_chroots_query(cls, copr_dir, mock_chroot_ids):
        """
        Return an SQL query returning all BuildChroots assigned to given CoprDir
        (copr_dir) and MockChroot's (mock_chroot_ids).  The output is sorted by
        Package.name, and then by Build.id (so callers can easily skip the
        uninteresting entries).
        """
        return (
            models.BuildChroot.query
            .join(models.Build)
            .join(models.Package)
            .options(
                load_only("build_id", "status", "mock_chroot_id", "result_dir"),
                contains_eager("build").load_only("package_id", "copr_dir_id",
                                                  "pkg_version")
                    .contains_eager("package").load_only("name"),
            )
            .filter(models.BuildChroot.mock_chroot_id.in_(mock_chroot_ids))
            .filter(models.Build.copr_dir==copr_dir)
            .order_by(
                models.Package.name.asc(),
                models.Build.id.desc(),
            )
        )

    @classmethod
    def package_build_chroots(cls, copr_dir):
        """
        For each Packge in CoprDir (copr_dir) and its assigned and enabled
        CoprChroots, return a list of the latest BuildChroots, if any.
        The output format is:
            [{
                "name": "PackageName",
                "chroots": [ <BuildChroot>, <BuildChroot>, ...  ],
            }, ...]
        """

        class _Finder:
            def __init__(self, find_mock_chroot_ids):
                self.searching_for = set(find_mock_chroot_ids)
                self.package_name = None
                self._reset()

            def _reset(self):
                self.mock_chroot_ids_found = set()
                self.package_name = None
                self.chroots = []

            def get_data(self):
                """
                Return the dictionary to be yielded, or None if no data are
                already processed.
                """
                if not self.chroots:
                    # no package in the result set
                    return None
                return {
                    "name": self.package_name,
                    "chroots": self.chroots,
                }

            def _add_item(self, build_chroot):
                self.mock_chroot_ids_found.add(build_chroot.mock_chroot_id)
                self.chroots.append(build_chroot)
                self.package_name = build_chroot.build.package.name

            def add(self, build_chroot):
                """
                Process one BuildChroot instance.  Return the get_data() output
                if we should flush the package out to caller, or None.
                """
                package_name = build_chroot.build.package.name

                if self.package_name is None:
                    # first package
                    self._add_item(build_chroot)
                    return None

                if package_name == self.package_name:
                    # additional chroot for the same package
                    mock_chroot_id = build_chroot.mock_chroot_id
                    if mock_chroot_id in self.mock_chroot_ids_found:
                        # we already have status for this
                        return None
                    self._add_item(build_chroot)
                    return None

                # a different package, flush the old one
                return_value = self.get_data()
                self._reset()
                self._add_item(build_chroot)
                return return_value

        mock_chroot_ids = {mch.id for mch in copr_dir.copr.active_chroots}
        package_data = _Finder(mock_chroot_ids)
        for bch in cls.package_build_chroots_query(copr_dir, mock_chroot_ids).yield_per(1000):
            if value := package_data.add(bch):
                yield value

        if value := package_data.get_data():
            yield value


    @classmethod
    def last_buildchroots(cls, pkg_ids, mock_chroot_ids):
        """
        Query the BuildChroot for given list of package IDs, and mock chroot IDs
        """
        builds_ids = (
            models.Build.query.join(models.BuildChroot)
                  .filter(models.Build.package_id.in_(pkg_ids))
                  .filter(models.BuildChroot.mock_chroot_id.in_(mock_chroot_ids))
                  .with_entities(
                      models.Build.package_id.label('package_id'),
                      func.max(models.Build.id).label('build_id').label("build_id"),
                      models.BuildChroot.mock_chroot_id,
                  )
                  .group_by(
                      models.Build.package_id,
                      models.BuildChroot.mock_chroot_id,
                  )
                  .subquery()
        )

        return (models.BuildChroot.query
            .join(
                builds_ids,
                and_(builds_ids.c.build_id == models.BuildChroot.build_id,
                     builds_ids.c.mock_chroot_id == models.BuildChroot.mock_chroot_id))
            .add_columns(
                builds_ids.c.package_id.label("package_id"),
            )
        )


    @classmethod
    def get_monitor_data(cls, copr, per_page=50, page=1,
                         paginate_if_more_than=1000):
        """
        Return Package objects with corresponding latest BuildChroots in active
        CoprChroots in given COPR.  We try to hold all packages on one page,
        though if there are more than PAGINATE_IF_MORE_THAN packages, we return
        only a slice of the results (in this case PAGE is used to return an
        appropriate slice, and PER_PAGE to control how many pieces are returned
        in one slice).
        We return only the pagination object:
            pagination.items => list of returned packages
            pagination.serverside_pagination => if the pagination is in effect
            pagination.item[N].latest_build_chroots => list of the latest
                BuildChroots (can span multiple Builds!) for the given package
        """

        packages_query = PackagesLogic.get_all_ordered(copr.id)
        packages_count = packages_query.count()

        if packages_count > paginate_if_more_than:
            pagination = packages_query.paginate(per_page=per_page,
                                                 page=page)
            pagination.serverside_pagination = True
        else:
            pagination = packages_query.paginate(per_page=paginate_if_more_than,
                                                 page=1)
            pagination.serverside_pagination = False

        pkg_ids = [package.id for package in pagination.items]
        mock_chroot_ids = [mch.id for mch in copr.active_chroots]

        query = BuildsMonitorLogic.last_buildchroots(pkg_ids, mock_chroot_ids)

        mapper = {}
        for package in pagination.items:
            mapper[package.id] = {}

        checkpoint("large query start")
        first = True
        for build_chroot, package_id in query:
            if first:
                checkpoint("large query done")
            first = False
            mapper[package_id][build_chroot.mock_chroot.name] = build_chroot

        checkpoint("buildchroot => package mapped")

        for package in pagination.items:
            package.latest_build_chroots = []
            for chroot in copr.active_chroots_sorted:
                package.latest_build_chroots.append(
                    mapper[package.id].get(chroot.name))

        return pagination
