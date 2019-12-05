import json
import time

from copr_common.enums import ActionTypeEnum, BackendResultEnum
from coprs import db
from coprs import models
from coprs import helpers
from coprs import exceptions


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

        for attr in ["result", "message", "ended_on"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(action, attr, value)

        db.session.add(action)

    @classmethod
    def send_createrepo(cls, copr, dirnames=None):
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
        data_dict = {
            "ownername": copr.owner_name,
            "projectname": copr.name,
            "project_dirnames": dirnames,
            "chroots": [chroot.name for chroot in copr.active_chroots],
        }
        action = models.Action(
            action_type=ActionTypeEnum("createrepo"),
            object_type="repository",
            object_id=0,
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
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

    @classmethod
    def get_chroot_builddirs(cls, build):
        """
        Creates a dictionary of chroot builddirs for build delete action
        :type build: models.build
        """
        chroot_builddirs = {'srpm-builds': build.result_dir}

        for build_chroot in build.build_chroots:
            chroot_builddirs[build_chroot.name] = build_chroot.result_dir

        return chroot_builddirs

    @classmethod
    def get_build_delete_data(cls, build):
        """
        Creates data needed for build delete action
        :type build: models.build
        """
        data = {
            "ownername": build.copr.owner_name,
            "projectname": build.copr_name,
        }

        if build.copr_dir:
            data["project_dirname"] = build.copr_dirname
        else:
            data["project_dirname"] = build.copr_name

        return data

    @classmethod
    def send_delete_build(cls, build):
        """
        Schedules build delete action
        :type build: models.Build
        """
        data = cls.get_build_delete_data(build)
        data["chroot_builddirs"] = cls.get_chroot_builddirs(build)

        action = models.Action(
            action_type=ActionTypeEnum("delete"),
            object_type="build",
            object_id=build.id,
            data=json.dumps(data),
            created_on=int(time.time())
        )
        db.session.add(action)

    @classmethod
    def send_delete_multiple_builds(cls, builds):
        """
        Schedules builds delete action for builds belonging to the same project
        :type build: list of models.Build
        """
        data = cls.get_build_delete_data(builds[0])
        data["builds"] = []
        for build in builds:
            chroot_builddirs = cls.get_chroot_builddirs(build)
            data["builds"].append(chroot_builddirs)

        action = models.Action(
            action_type=ActionTypeEnum("delete"),
            object_type="builds",
            data=json.dumps(data),
            created_on=int(time.time())
        )
        db.session.add(action)

    @classmethod
    def send_cancel_build(cls, build):
        """ Schedules build cancel action
        :type build: models.Build
        """
        for chroot in build.build_chroots:
            if chroot.state != "running":
                continue

            data_dict = {
                "task_id": chroot.task_id,
            }

            action = models.Action(
                action_type=ActionTypeEnum("cancel_build"),
                data=json.dumps(data_dict),
                created_on=int(time.time())
            )
            db.session.add(action)

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

    @classmethod
    def send_create_gpg_key(cls, copr):
        """
        :type copr: models.Copr
        """

        data_dict = {
            "ownername": copr.owner_name,
            "projectname": copr.name,
        }

        action = models.Action(
            action_type=ActionTypeEnum("gen_gpg_key"),
            object_type="copr",
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
        db.session.add(action)

    @classmethod
    def send_rawhide_to_release(cls, data):
        action = models.Action(
            action_type=ActionTypeEnum("rawhide_to_release"),
            object_type="None",
            data=json.dumps(data),
            created_on=int(time.time()),
        )
        db.session.add(action)

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
