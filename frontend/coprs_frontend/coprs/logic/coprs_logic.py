import time

from sqlalchemy import and_
from sqlalchemy.event import listen
from sqlalchemy.orm.attributes import NEVER_SET

from coprs import db
from coprs import exceptions
from coprs import helpers
from coprs import models
from coprs.logic import users_logic

from coprs.logic.actions_logic import ActionsLogic


class CoprsLogic(object):
    """
    Used for manipulating Coprs.

    All methods accept user object as a first argument,
    as this may be needed in future.
    """

    @classmethod
    def get_all(cls):
        """ Return all coprs without those which are deleted. """
        query = (db.session.query(models.Copr)
                 .join(models.Copr.owner)
                 .options(db.contains_eager(models.Copr.owner))
                 .filter(models.Copr.deleted == False))
        return query

    @classmethod
    def get(cls, user, username, coprname, **kwargs):
        with_builds = kwargs.get("with_builds", False)
        with_mock_chroots = kwargs.get("with_mock_chroots", False)

        query = (
            cls.get_all()
            .filter(models.Copr.name == coprname)
            .filter(models.User.username == username)
        )

        if with_builds:
            query = (query.outerjoin(models.Copr.builds)
                     .options(db.contains_eager(models.Copr.builds))
                     .order_by(models.Build.submitted_on.desc()))

        if with_mock_chroots:
            query = (query.outerjoin(*models.Copr.mock_chroots.attr)
                     .options(db.contains_eager(*models.Copr.mock_chroots.attr))
                     .order_by(models.MockChroot.os_release.asc())
                     .order_by(models.MockChroot.os_version.asc())
                     .order_by(models.MockChroot.arch.asc()))

        return query

    @classmethod
    def get_multiple(cls, user, **kwargs):
        user_relation = kwargs.get("user_relation", None)
        username = kwargs.get("username", None)
        with_mock_chroots = kwargs.get("with_mock_chroots", None)
        with_builds = kwargs.get("with_builds", None)
        incl_deleted = kwargs.get("incl_deleted", None)
        ids = kwargs.get("ids", None)

        query = (db.session.query(models.Copr)
                 .join(models.Copr.owner)
                 .options(db.contains_eager(models.Copr.owner))
                 .order_by(models.Copr.id.desc()))

        if not incl_deleted:
            query = query.filter(models.Copr.deleted == False)

        if isinstance(ids, list):  # can be an empty list
            query = query.filter(models.Copr.id.in_(ids))

        if user_relation == "owned":
            query = query.filter(
                models.User.username == username)
        elif user_relation == "allowed":
            aliased_user = db.aliased(models.User)

            query = (query.join(models.CoprPermission,
                                models.Copr.copr_permissions)
                     .filter(models.CoprPermission.copr_builder ==
                             helpers.PermissionEnum('approved'))
                     .join(aliased_user, models.CoprPermission.user)
                     .filter(aliased_user.username == username))

        if with_mock_chroots:
            query = (query.outerjoin(*models.Copr.mock_chroots.attr)
                     .options(db.contains_eager(*models.Copr.mock_chroots.attr))
                     .order_by(models.MockChroot.os_release.asc())
                     .order_by(models.MockChroot.os_version.asc())
                     .order_by(models.MockChroot.arch.asc()))

        if with_builds:
            query = (query.outerjoin(models.Copr.builds)
                     .options(db.contains_eager(models.Copr.builds))
                     .order_by(models.Build.submitted_on.desc()))

        return query

    @classmethod
    def get_playground(cls):
        return cls.get_all().filter(models.Copr.playground == True)

    @classmethod
    def set_playground(cls, user, copr):
        if user.admin:
            db.session.add(copr)
            pass
        else:
            raise exceptions.InsufficientRightsException(
                "User is not a system admin")

    @classmethod
    def get_multiple_fulltext(cls, search_string):
        query = (models.Copr.query.join(models.User)
                 .filter(models.Copr.deleted == False))
        if "/" in search_string:
            # searching for user/project
            name = "%{}%".format(search_string.split("/")[0])
            project = "%{}%".format(search_string.split("/")[1])
            query = query.filter(and_(models.User.username.ilike(name),
                                      models.Copr.name.ilike(project)))
        else:
            # fulltext search
            query = query.whooshee_search(search_string)
        return query

    @classmethod
    def add(cls, user, name, repos, selected_chroots, description,
            instructions, check_for_duplicates=False, **kwargs):
        copr = models.Copr(name=name,
                           repos=repos,
                           owner_id=user.id,
                           description=description,
                           instructions=instructions,
                           created_on=int(time.time()),
                           **kwargs)

        # form validation checks for duplicates
        CoprsLogic.new(user, copr,
                       check_for_duplicates=check_for_duplicates)
        CoprChrootsLogic.new_from_names(user, copr,
                                        selected_chroots)
        return copr

    @classmethod
    def new(cls, user, copr, check_for_duplicates=True):
        if check_for_duplicates and cls.exists_for_user(user, copr.name).all():
            raise exceptions.DuplicateException(
                "Copr: '{0}' already exists".format(copr.name))
        db.session.add(copr)

    @classmethod
    def update(cls, user, copr, check_for_duplicates=True):
        cls.raise_if_unfinished_blocking_action(
            user, copr, "Can't change this project name,"
                        " another operation is in progress: {action}")

        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr, "Only owners and admins may update their projects.")

        existing = cls.exists_for_user(copr.owner, copr.name).first()
        if existing:
            if check_for_duplicates and existing.id != copr.id:
                raise exceptions.DuplicateException(
                    "Project: '{0}' already exists".format(copr.name))

        else:  # we're renaming
            # if we fire a models.Copr.query, it will use the modified copr in session
            # -> workaround this by just getting the name
            old_copr_name = (db.session.query(models.Copr.name)
                             .filter(models.Copr.id == copr.id)
                             .filter(models.Copr.deleted == False)
                             .first()[0])

            action = models.Action(action_type=helpers.ActionTypeEnum("rename"),
                                   object_type="copr",
                                   object_id=copr.id,
                                   old_value="{0}/{1}".format(copr.owner.name,
                                                              old_copr_name),
                                   new_value="{0}/{1}".format(copr.owner.name,
                                                              copr.name),
                                   created_on=int(time.time()))
            db.session.add(action)
        db.session.add(copr)

    @classmethod
    def delete(cls, user, copr, check_for_duplicates=True):
        cls.raise_if_cant_delete(user, copr)
        # TODO: do we want to dump the information somewhere, so that we can
        # search it in future?
        cls.raise_if_unfinished_blocking_action(
            user, copr, "Can't delete this project,"
                        " another operation is in progress: {action}")

        action = models.Action(action_type=helpers.ActionTypeEnum("delete"),
                               object_type="copr",
                               object_id=copr.id,
                               old_value="{0}/{1}".format(copr.owner.name,
                                                          copr.name),
                               new_value="",
                               created_on=int(time.time()))
        copr.deleted = True

        db.session.add(action)

        return copr

    @classmethod
    def exists_for_user(cls, user, coprname, incl_deleted=False):
        existing = (models.Copr.query
                    .filter(models.Copr.name == coprname)
                    .filter(models.Copr.owner_id == user.id))

        if not incl_deleted:
            existing = existing.filter(models.Copr.deleted == False)

        return existing

    @classmethod
    def unfinished_blocking_actions_for(cls, user, copr):
        blocking_actions = [helpers.ActionTypeEnum("rename"),
                            helpers.ActionTypeEnum("delete")]

        actions = (models.Action.query
                   .filter(models.Action.object_type == "copr")
                   .filter(models.Action.object_id == copr.id)
                   .filter(models.Action.result ==
                           helpers.BackendResultEnum("waiting"))
                   .filter(models.Action.action_type.in_(blocking_actions)))

        return actions

    @classmethod
    def raise_if_unfinished_blocking_action(cls, user, copr, message):
        """
        Raise ActionInProgressException if given copr has an unfinished
        action. Return None otherwise.
        """

        unfinished_actions = cls.unfinished_blocking_actions_for(
            user, copr).all()
        if unfinished_actions:
            raise exceptions.ActionInProgressException(
                message, unfinished_actions[0])

    @classmethod
    def raise_if_cant_delete(cls, user, copr):
        """
        Raise InsufficientRightsException if given copr cant be deleted
        by given user. Return None otherwise.
        """

        if not user.admin and user != copr.owner:
            raise exceptions.InsufficientRightsException(
                "Only owners may delete their projects.")


class CoprPermissionsLogic(object):
    @classmethod
    def get(cls, user, copr, searched_user):
        query = (models.CoprPermission.query
                 .filter(models.CoprPermission.copr == copr)
                 .filter(models.CoprPermission.user == searched_user))

        return query

    @classmethod
    def get_for_copr(cls, user, copr):
        query = models.CoprPermission.query.filter(
            models.CoprPermission.copr == copr)

        return query

    @classmethod
    def new(cls, user, copr_permission):
        db.session.add(copr_permission)

    @classmethod
    def update_permissions(cls, user, copr, copr_permission,
                           new_builder, new_admin):

        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr, "Only owners and admins may update"
                        " their projects permissions.")

        (models.CoprPermission.query
         .filter(models.CoprPermission.copr_id == copr.id)
         .filter(models.CoprPermission.user_id == copr_permission.user_id)
         .update({"copr_builder": new_builder,
                  "copr_admin": new_admin}))

    @classmethod
    def update_permissions_by_applier(cls, user, copr, copr_permission, new_builder, new_admin):
        if copr_permission:
            # preserve approved permissions if set
            if (not new_builder or
                    copr_permission.copr_builder != helpers.PermissionEnum("approved")):

                copr_permission.copr_builder = new_builder

            if (not new_admin or
                    copr_permission.copr_admin != helpers.PermissionEnum("approved")):

                copr_permission.copr_admin = new_admin
        else:
            perm = models.CoprPermission(
                user=user,
                copr=copr,
                copr_builder=new_builder,
                copr_admin=new_admin)

            cls.new(user, perm)

    @classmethod
    def delete(cls, user, copr_permission):
        db.session.delete(copr_permission)


def on_auto_createrepo_change(target_copr, value_acr, old_value_acr, initiator):
    """ Emit createrepo action when auto_createrepo re-enabled"""
    if old_value_acr == NEVER_SET:
        #  created new copr, not interesting
        return
    if not old_value_acr and value_acr:
        #  re-enabled
        ActionsLogic.send_createrepo(
            target_copr.owner.name,
            target_copr.name,
            chroots=[chroot.name for chroot in target_copr.active_chroots]
        )


listen(models.Copr.auto_createrepo, 'set', on_auto_createrepo_change,
       active_history=True, retval=False)


class CoprChrootsLogic(object):
    @classmethod
    def mock_chroots_from_names(cls, user, names):
        db_chroots = models.MockChroot.query.all()
        mock_chroots = []
        for ch in db_chroots:
            if ch.name in names:
                mock_chroots.append(ch)

        return mock_chroots

    @classmethod
    def new(cls, user, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def new_from_names(cls, user, copr, names):
        for mock_chroot in cls.mock_chroots_from_names(user, names):
            db.session.add(
                models.CoprChroot(copr=copr, mock_chroot=mock_chroot))

    @classmethod
    def update_buildroot_pkgs(cls, copr, chroot, buildroot_pkgs):
        copr_chroot = copr.check_copr_chroot(chroot)
        if copr_chroot:
            copr_chroot.buildroot_pkgs = buildroot_pkgs
            db.session.add(copr_chroot)

    @classmethod
    def update_from_names(cls, user, copr, names):
        current_chroots = copr.mock_chroots
        new_chroots = cls.mock_chroots_from_names(user, names)
        # add non-existing
        for mock_chroot in new_chroots:
            if mock_chroot not in current_chroots:
                db.session.add(
                    models.CoprChroot(copr=copr, mock_chroot=mock_chroot))

        # delete no more present
        to_remove = []
        for mock_chroot in current_chroots:
            if mock_chroot not in new_chroots:
                # can't delete here, it would change current_chroots and break
                # iteration
                to_remove.append(mock_chroot)

        for mc in to_remove:
            copr.mock_chroots.remove(mc)


class MockChrootsLogic(object):
    @classmethod
    def get(cls, user, os_release, os_version, arch, active_only=False, noarch=False):
        if noarch and not arch:
            return (models.MockChroot.query
                    .filter(models.MockChroot.os_release == os_release,
                            models.MockChroot.os_version == os_version))

        return (models.MockChroot.query
                .filter(models.MockChroot.os_release == os_release,
                        models.MockChroot.os_version == os_version,
                        models.MockChroot.arch == arch))

    @classmethod
    def get_from_name(cls, chroot_name, active_only=False, noarch=False):
        """
        chroot_name should be os-version-architecture, e.g. fedora-rawhide-x86_64
        the architecture could be optional with noarch=True

        Return MockChroot object for textual representation of chroot
        """

        name_tuple = cls.tuple_from_name(None, chroot_name, noarch=noarch)
        return cls.get(None, name_tuple[0], name_tuple[1], name_tuple[2],
                       active_only=active_only, noarch=noarch)

    @classmethod
    def get_multiple(cls, user, active_only=False):
        query = models.MockChroot.query
        if active_only:
            query = query.filter(models.MockChroot.is_active == True)
        return query

    @classmethod
    def add(cls, user, name):
        name_tuple = cls.tuple_from_name(user, name)
        if cls.get(user, *name_tuple).first():
            raise exceptions.DuplicateException(
                "Mock chroot with this name already exists.")
        new_chroot = models.MockChroot(os_release=name_tuple[0],
                                       os_version=name_tuple[1],
                                       arch=name_tuple[2])
        cls.new(user, new_chroot)
        return new_chroot

    @classmethod
    def new(cls, user, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def edit_by_name(cls, user, name, is_active):
        name_tuple = cls.tuple_from_name(user, name)
        mock_chroot = cls.get(user, *name_tuple).first()
        if not mock_chroot:
            raise exceptions.NotFoundException(
                "Mock chroot with this name doesn't exist.")

        mock_chroot.is_active = is_active
        cls.update(user, mock_chroot)
        return mock_chroot

    @classmethod
    def update(cls, user, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def delete_by_name(cls, user, name):
        name_tuple = cls.tuple_from_name(user, name)
        mock_chroot = cls.get(user, *name_tuple).first()
        if not mock_chroot:
            raise exceptions.NotFoundException(
                "Mock chroot with this name doesn't exist.")

        cls.delete(user, mock_chroot)

    @classmethod
    def delete(cls, user, mock_chroot):
        db.session.delete(mock_chroot)

    @classmethod
    def tuple_from_name(cls, user, name, noarch=False):
        """
        input should be os-version-architecture, e.g. fedora-rawhide-x86_64

        the architecture could be optional with noarch=True

        returns ("os", "version", "arch") or ("os", "version", None)
        """
        split_name = name.split("-")
        valid = False
        if noarch and len(split_name) in [2, 3]:
            valid = True
        if not noarch and len(split_name) == 3:
            valid = True

        if not valid:
            raise exceptions.MalformedArgumentException(
                "Chroot name is not valid")

        if noarch and len(split_name) == 2:
            split_name.append(None)

        return tuple(split_name)
