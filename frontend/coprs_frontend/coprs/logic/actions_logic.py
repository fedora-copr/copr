import json
import time

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from copr_common.enums import ActionTypeEnum, BackendResultEnum
from coprs import db
from coprs import models
from coprs import helpers
from coprs import exceptions
from .helpers import get_graph_parameters

class ActionsLogic(object):

    @classmethod
    def get(cls, action_id):
        """
        Return single action identified by `action_id`
        """

        query = models.Action.query.filter(models.Action.id == action_id)
        return query

    @classmethod
    def get_many(cls, action_type=None, result=None):
        query = models.Action.query
        if action_type is not None:
            query = query.filter(models.Action.action_type ==
                                 int(action_type))
        if result is not None:
            query = query.filter(models.Action.result ==
                                 int(result))

        return query

    @classmethod
    def get_waiting(cls):
        """
        Return actions that aren't finished
        """

        query = (models.Action.query
                 .filter(models.Action.result ==
                         BackendResultEnum("waiting"))
                 .filter(models.Action.action_type !=
                         ActionTypeEnum("legal-flag"))
                 .order_by(models.Action.created_on.asc()))

        return query

    @classmethod
    def get_by_ids(cls, ids):
        """
        Return actions matching passed `ids`
        """

        return models.Action.query.filter(models.Action.id.in_(ids))

    @classmethod
    def update_state_from_dict(cls, action, upd_dict):
        """
        Update `action` object with `upd_dict` data

        Updates result, message and ended_on parameters.
        """

        for attr in ["result", "message"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(action, attr, value)

        if upd_dict.get('result', None) in [BackendResultEnum("success"),
                                            BackendResultEnum("failure")]:
            action.ended_on = time.time()
        db.session.add(action)
        return action

    @classmethod
    def send_createrepo(cls, copr, dirnames=None, chroots=None, devel=None,
                        priority=None):
        """
        Create a new createrepo Action in queue for given copr.

        :param copr: Copr ORM object.
        :param dirnames: List of CoprDir *names* to run the createrepo in.
            Optional, use only when we want to limit the scope of this action,
            otherwise the createrepo action is run in all dirnames.
        :param chroots: List of MockChroot *names*.  Optional, by default
            createrepo is run in all active chroots.
        :param devel: If devel=True, the createrepo action is run only in the
            devel/ subdirectory, if devel=False the createrepo is run in the
            "production" directory.  When devel=None, depending on the current
            auto_createrepo settings, both production and devel might be
            regenerated.
        """
        possible_dirnames = [copr_dir.name for copr_dir in copr.dirs]
        if not dirnames:
            # by default we createrepo for all of them
            dirnames = possible_dirnames
        else:
            missing = set(dirnames) - set(possible_dirnames)
            if missing:
                raise exceptions.NotFoundException(
                    "Can't createrepo for {} dirnames in {} project".format(
                        missing, copr.full_name))

        if chroots is None:
            chroots = [chroot.name for chroot in copr.active_chroots]

        data_dict = {
            "ownername": copr.owner_name,
            "projectname": copr.name,
            "project_dirnames": dirnames,
            "chroots": chroots,
            "appstream": copr.appstream,
        }

        run_in = set()
        if devel is None:
            run_in.add('prod')
            if not copr.auto_createrepo:
                run_in.add('dev')
        else:
            run_in.add('dev' if devel else 'prod')

        for run in run_in:
            data_dict["devel"] = run == "dev"
            action = models.Action(
                action_type=ActionTypeEnum("createrepo"),
                object_type="repository",
                object_id=0,
                data=json.dumps(data_dict),
                created_on=int(time.time()),
            )
            if priority is not None:
                action.priority = priority
            db.session.add(action)


    @classmethod
    def send_delete_copr(cls, copr):
        data_dict = {
            "ownername": copr.owner_name,
            "project_dirnames": [copr_dir.name for copr_dir in copr.dirs],
        }
        action = models.Action(action_type=ActionTypeEnum("delete"),
                               object_type="copr",
                               object_id=copr.id,
                               data=json.dumps(data_dict),
                               created_on=int(time.time()))
        db.session.add(action)
        return action

    @classmethod
    def get_chroot_builddirs(cls, build):
        """
        Creates a dictionary of chroot builddirs for build delete action
        :type build: models.build
        """
        chroot_builddirs = {}

        # plan to remove sub-dir in srpm-builds/ directory
        if build.result_dir:
            chroot_builddirs['srpm-builds'] = [build.result_dir]

        # and all chroot sub-dirs
        for build_chroot in build.build_chroots:
            if not build_chroot.result_dir:
                # when we cancel build when the src.rpm (e.g. SCM method) is not
                # yet generated
                continue
            chroot_builddirs[build_chroot.name] = [build_chroot.result_dir]

        return chroot_builddirs

    @classmethod
    def get_build_delete_data(cls, build):
        """
        Creates data needed for build delete action
        :type build: models.build
        """
        return {
            "ownername": build.copr.owner_name,
            "projectname": build.copr_name,
            "project_dirname":
                build.copr_dirname if build.copr_dir else build.copr_name,
            "chroot_builddirs": cls.get_chroot_builddirs(build),
            "appstream": build.appstream,
        }

    @classmethod
    def send_delete_build(cls, build):
        """
        Schedules build delete action
        :type build: models.Build
        """
        action = models.Action(
            action_type=ActionTypeEnum("delete"),
            object_type="build",
            object_id=build.id,
            data=json.dumps(cls.get_build_delete_data(build)),
            created_on=int(time.time())
        )
        db.session.add(action)
        return action

    @classmethod
    def send_delete_multiple_builds(cls, builds):
        """
        Schedules builds delete action for builds belonging to the same project
        :type build: list of models.Build
        """
        project_dirnames = {}
        data = {'project_dirnames': project_dirnames}

        build_ids = []
        for build in builds:
            build_delete_data = cls.get_build_delete_data(build)
            build_ids.append(build.id)

            # inherit some params from the first build
            for param in ["ownername", "projectname", "appstream"]:
                new = build_delete_data[param]
                if param in data and data[param] != new:
                    # this shouldn't happen
                    raise exceptions.BadRequest("Can not delete builds "
                                                "from more projects")
                data[param] = new

            dirname = build_delete_data['project_dirname']
            if not dirname in project_dirnames:
                project_dirnames[dirname] = {}

            project_dirname = project_dirnames[dirname]
            for chroot, subdirs in build_delete_data['chroot_builddirs'].items():
                if chroot not in project_dirname:
                    project_dirname[chroot] = subdirs
                else:
                    project_dirname[chroot].extend(subdirs)

        data['build_ids'] = build_ids

        # not object_id here, we are working with multiple IDs
        action = models.Action(
            action_type=ActionTypeEnum("delete"),
            object_type="builds",
            data=json.dumps(data),
            created_on=int(time.time())
        )
        db.session.add(action)
        return action

    @classmethod
    def send_cancel_build(cls, build):
        """
        Schedule build cancel.  The build is marked as canceled immediately, but
        to not waste the resources we propagate this information to Backend
        which may deallocate the builder resources.

        :type build: models.Build
        """
        if build.canceled:
            return
        db.session.add(models.CancelRequest(what=str(build.id)))
        for chroot in build.build_chroots:
            db.session.add(models.CancelRequest(what=chroot.task_id))

    @classmethod
    def send_update_comps(cls, chroot):
        """ Schedules update comps.xml action

        :type copr_chroot: models.CoprChroot
        """

        url_path = helpers.copr_url("coprs_ns.chroot_view_comps", chroot.copr, chrootname=chroot.name)
        data_dict = {
            "ownername": chroot.copr.owner_name,
            "projectname": chroot.copr.name,
            "chroot": chroot.name,
            "comps_present": chroot.comps_zlib is not None,
            "url_path": url_path,
        }

        action = models.Action(
            action_type=ActionTypeEnum("update_comps"),
            object_type="copr_chroot",
            data=json.dumps(data_dict),
            created_on=int(time.time())
        )
        db.session.add(action)
        return action

    @classmethod
    def send_create_gpg_key(cls, copr):
        """
        :type copr: models.Copr
        """

        data_dict = {
            "ownername": copr.owner_name,
            "projectname": copr.name,
            "appstream": copr.appstream,
        }

        action = models.Action(
            action_type=ActionTypeEnum("gen_gpg_key"),
            object_type="copr",
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
        db.session.add(action)
        return action

    @classmethod
    def send_rawhide_to_release(cls, data):
        action = models.Action(
            action_type=ActionTypeEnum("rawhide_to_release"),
            object_type="None",
            data=json.dumps(data),
            created_on=int(time.time()),
        )
        db.session.add(action)
        return action

    @classmethod
    def send_fork_copr(cls, src, dst, builds_map):
        """
        :type src: models.Copr
        :type dst: models.Copr
        :type builds_map: dict where keys are forked builds IDs and values are IDs from the original builds.
        """

        action = models.Action(
            action_type=ActionTypeEnum("fork"),
            object_type="copr",
            old_value="{0}".format(src.full_name),
            new_value="{0}".format(dst.full_name),
            data=json.dumps({"user": dst.owner_name, "copr": dst.name, "builds_map": builds_map}),
            created_on=int(time.time()),
        )
        db.session.add(action)
        return action

    @classmethod
    def send_build_module(cls, copr, module):
        """
        :type copr: models.Copr
        :type modulemd: str content of module yaml file
        """

        mock_chroots = set.intersection(*[set(b.chroots) for b in module.builds])
        data = {
            "chroots": [ch.name for ch in mock_chroots],
            "builds": [b.id for b in module.builds],
            "appstream": copr.appstream,
        }

        action = models.Action(
            action_type=ActionTypeEnum("build_module"),
            object_type="module",
            object_id=module.id,
            old_value="",
            new_value="",
            data=json.dumps(data),
            created_on=int(time.time()),
        )
        db.session.add(action)
        return action

    @classmethod
    def send_delete_chroot(cls, copr_chroot):
        """
        Schedules deletion of a chroot directory from project
        Useful to remove outdated chroots
        :type build: models.CoprChroot
        """
        data_dict = {
            "ownername": copr_chroot.copr.owner_name,
            "projectname": copr_chroot.copr.name,
            "chrootname": copr_chroot.name,
        }

        action = models.Action(
            action_type=ActionTypeEnum("delete"),
            object_type="chroot",
            object_id=None,
            data=json.dumps(data_dict),
            created_on=int(time.time())
        )
        db.session.add(action)
        return action

    @classmethod
    def cache_action_graph_data(cls, type, time, waiting, success, failure):
        result = models.ActionsStatistics.query\
                .filter(models.ActionsStatistics.stat_type == type)\
                .filter(models.ActionsStatistics.time == time).first()
        if result:
            return

        try:
            cached_data = models.ActionsStatistics(
                time = time,
                stat_type = type,
                waiting = waiting,
                success = success,
                failed = failure
            )
            db.session.add(cached_data)
            db.session.commit()  # @FIXME We should not commit here
        except IntegrityError: # other process already calculated the graph data and cached it
            db.session.rollback()

    @classmethod
    def get_actions_bucket(cls, start, end, actionType):
        if actionType == 0:
            # used for getting data for "processed" line of action graphs
            result = models.Action.query\
                .filter(and_(
                    models.Action.created_on <= end,
                    or_(
                        models.Action.ended_on > start,
                        models.Action.ended_on == None
                    )))\
                .count()
            return result

        else:
            # used to getting data for "successed and failure" line of action graphs
            result = models.Action.query\
                .filter(models.Action.ended_on <= end)\
                .filter(models.Action.ended_on > start)\
                .filter(models.Action.result == actionType)\
                .count()
            return result

    @classmethod
    def get_cached_action_data(cls, params):
        data = {
            "waiting": [],
            "success": [],
            "failure": [],
        }
        result = models.ActionsStatistics.query\
            .filter(models.ActionsStatistics.stat_type == params["type"])\
            .filter(models.ActionsStatistics.time >= params["start"])\
            .filter(models.ActionsStatistics.time <= params["end"])\
            .order_by(models.ActionsStatistics.time)
        for row in result:
            data["waiting"].append(row.waiting)
            data["success"].append(row.success)
            data["failure"].append(row.failed)

        return data

    @classmethod
    def get_action_graph_data(cls, type):
        data = [["processed"], ["success"], ["failure"], ["time"] ]
        params = get_graph_parameters(type)
        cached_data = cls.get_cached_action_data(params)
        for actionType in ["waiting", "success", "failure"]:
            data[BackendResultEnum(actionType)].extend(cached_data[actionType])
        for i in range(len(data[0]) - 1, params["steps"]):
            step_start = params["start"] + i * params["step"]
            step_end = step_start + params["step"]
            waiting = cls.get_actions_bucket(step_start, step_end, BackendResultEnum("waiting"))
            success = cls.get_actions_bucket(step_start, step_end, BackendResultEnum("success"))
            failure = cls.get_actions_bucket(step_start, step_end, BackendResultEnum("failure"))
            data[0].append(waiting)
            data[1].append(success)
            data[2].append(failure)
            cls.cache_action_graph_data(type, time=step_start, waiting=waiting, success=success, failure=failure)

        for i in range(params["start"], params["end"], params["step"]):
            data[3].append(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(i)))

        return data
