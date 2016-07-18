import json
import time
from coprs import db
from coprs import models
from coprs import helpers


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
                         helpers.BackendResultEnum("waiting"))
                 .filter(models.Action.action_type !=
                         helpers.ActionTypeEnum("legal-flag"))
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
    def send_createrepo(cls, username, coprname, chroots):
        data_dict = {
            "username": username,
            "projectname": coprname,
            "chroots": chroots
        }
        action = models.Action(
            action_type=helpers.ActionTypeEnum("createrepo"),
            object_type="None",
            object_id=0,
            old_value="",
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
        db.session.add(action)

    @classmethod
    def send_delete_build(cls, build):
        """ Schedules build delete action
        :type build: models.Build
        """
        # don't delete skipped chroots
        chroots_to_delete = [
            chroot.name for chroot in build.build_chroots
            if chroot.state not in ["skipped"]
        ]
        if len(chroots_to_delete) == 0:
            return

        data_dict = {
            "username": build.copr.user.name,
            "projectname": build.copr.name,
            "chroots": chroots_to_delete
        }

        if build.is_older_results_naming_used:
            if build.src_pkg_name is None or build.src_pkg_name == "":
                return
            data_dict["src_pkg_name"] = build.src_pkg_name
        else:
            data_dict["result_dir_name"] = build.result_dir_name

        action = models.Action(
            action_type=helpers.ActionTypeEnum("delete"),
            object_type="build",
            object_id=build.id,
            old_value=build.copr.full_name,
            data=json.dumps(data_dict),
            created_on=int(time.time())
        )
        db.session.add(action)

    @classmethod
    def send_update_comps(cls, chroot):
        """ Schedules update comps.xml action

        :type copr_chroot: models.CoprChroot
        """

        data_dict = {
            "username": chroot.copr.user.name,
            "projectname": chroot.copr.name,
            "chroot": chroot.name,
            "comps_present": chroot.comps_zlib is not None,
        }

        action = models.Action(
            action_type=helpers.ActionTypeEnum("update_comps"),
            object_type="copr_chroot",
            data=json.dumps(data_dict),
            created_on=int(time.time())
        )
        db.session.add(action)

    @classmethod
    def send_update_module_md(cls, chroot):
        """ Schedules update module_md.yaml action

        :type copr_chroot: models.CoprChroot
        """
        data_dict = {
            "username": chroot.copr.user.name,
            "projectname": chroot.copr.name,
            "chroot": chroot.name,
            "module_md_present": chroot.module_md_zlib is not None,
        }

        action = models.Action(
            action_type=helpers.ActionTypeEnum("update_module_md"),
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
            "username": copr.user.name,
            "projectname": copr.name,
        }

        action = models.Action(
            action_type=helpers.ActionTypeEnum("gen_gpg_key"),
            object_type="copr",
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
        db.session.add(action)

    @classmethod
    def send_rawhide_to_release(cls, data):
        action = models.Action(
            action_type=helpers.ActionTypeEnum("rawhide_to_release"),
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
            action_type=helpers.ActionTypeEnum("fork"),
            object_type="copr",
            old_value="{0}".format(src.full_name),
            new_value="{0}".format(dst.full_name),
            data=json.dumps({"user": dst.owner_name, "copr": dst.name, "builds_map": builds_map}),
            created_on=int(time.time()),
        )
        db.session.add(action)
