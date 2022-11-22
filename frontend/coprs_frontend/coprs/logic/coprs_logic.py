import locale
import json
import os
import time
import datetime
from functools import cmp_to_key
from itertools import zip_longest

import flask

from sqlalchemy import not_
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy.event import listens_for
from sqlalchemy.orm.attributes import NEVER_SET, NO_VALUE
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.attributes import get_history

from copr_common.enums import ActionTypeEnum, BackendResultEnum, ActionPriorityEnum
from coprs import app, db
from coprs import exceptions
from coprs import helpers
from coprs import models
from coprs import logic
from coprs.exceptions import MalformedArgumentException, BadRequest
from coprs.logic import users_logic
from coprs.whoosheers import CoprWhoosheer
from coprs.helpers import fix_protocol_for_backend, clone_sqlalchemy_instance

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
                 .join(models.Copr.user)
                 .options(db.contains_eager(models.Copr.user))
                 .filter(models.Copr.deleted == False))
        return query

    @classmethod
    def get_by_id(cls, copr_id):
        return cls.get_all().filter(models.Copr.id == copr_id)

    @classmethod
    def attach_build(cls, query):
        query = (query.outerjoin(models.Copr.builds)
                 .options(db.contains_eager(models.Copr.builds))
                 .order_by(models.Build.submitted_on.desc()))
        return query

    @classmethod
    def attach_mock_chroots(cls, query):
        query = (query.outerjoin(*models.Copr.mock_chroots.attr)
                 .options(db.contains_eager(*models.Copr.mock_chroots.attr))
                 .order_by(models.MockChroot.os_release.asc())
                 .order_by(models.MockChroot.os_version.asc())
                 .order_by(models.MockChroot.arch.asc()))
        return query

    @classmethod
    def get_multiple_by_username(cls, username, **kwargs):
        with_builds = kwargs.get("with_builds", False)
        with_mock_chroots = kwargs.get("with_mock_chroots", False)

        query = (
            cls.get_all()
            .filter(models.User.username == username)
        )

        if with_builds:
            query = cls.attach_build(query)

        if with_mock_chroots:
            query = cls.attach_mock_chroots(query)

        return query

    @classmethod
    def get_multiple_by_group_id(cls, group_id, **kwargs):
        with_builds = kwargs.get("with_builds", False)
        with_mock_chroots = kwargs.get("with_mock_chroots", False)

        query = (
            cls.get_all()
            .filter(models.Copr.group_id == group_id)
        )

        if with_builds:
            query = cls.attach_build(query)

        if with_mock_chroots:
            query = cls.attach_mock_chroots(query)

        return query

    @classmethod
    def get(cls, username, coprname, **kwargs):
        query = cls.get_multiple_by_username(username, **kwargs)
        query = query.filter(models.Copr.name == coprname)
        return query

    @classmethod
    def get_by_group_id(cls, group_id, coprname, **kwargs):
        query = cls.get_multiple_by_group_id(group_id, **kwargs)
        query = query.filter(models.Copr.name == coprname)
        return query

    @classmethod
    def get_multiple(cls, include_deleted=False, include_unlisted_on_hp=True):
        query = (
            db.session.query(models.Copr)
            .join(models.Copr.user)
            .outerjoin(models.Group)
            .options(db.contains_eager(models.Copr.user))
        )

        if not include_deleted:
            query = query.filter(models.Copr.deleted.is_(False))

        if not include_unlisted_on_hp:
            query = query.filter(models.Copr.unlisted_on_hp.is_(False))

        return query

    @classmethod
    def set_query_order(cls, query, desc=False):
        if desc:
            query = query.order_by(models.Copr.id.desc())
        else:
            query = query.order_by(models.Copr.id.asc())
        return query

    # user_relation="owned", username=username, with_mock_chroots=False
    @classmethod
    def get_multiple_owned_by_username(cls, username, include_unlisted_on_hp=True):
        query = cls.get_multiple(include_unlisted_on_hp=include_unlisted_on_hp)
        return query.filter(models.User.username == username)

    @classmethod
    def filter_by_user_name(cls, query, username):
        # should be already joined with the User table
        return query.filter(models.User.username == username)

    @classmethod
    def filter_by_group_name(cls, query, group_name):
        # should be already joined with the Group table
        return query.filter(models.Group.name == group_name)

    @classmethod
    def filter_without_group_projects(cls, query):
        return query.filter(models.Copr.group_id.is_(None))

    @classmethod
    def filter_by_ownername(cls, query, ownername):
        """
        Filter cls.get_multiple()-like QUERY by OWNERNAME (either '@groupname'
        or 'username').
        """
        if ownername.startswith("@"):
            group_name = ownername[1:]
            return cls.filter_by_group_name(query, group_name)
        query = query.filter(models.User.username==ownername)
        return cls.filter_without_group_projects(query)

    @classmethod
    def get_by_ownername(cls, ownername):
        """
        Return a query for list of projects owned by OWNERNAME (either
        '@groupname' or 'username').
        """
        query = cls.get_multiple()
        return cls.filter_by_ownername(query, ownername)

    @classmethod
    def get_by_ownername_coprname(cls, ownername, coprname):
        """
        Return a Copr object owned by OWNERNAME (either '@groupname' or
        'username') with a name COPRNAME.
        """
        try:
            return cls.get_by_ownername(ownername).filter(models.Copr.name==coprname).one()
        except NoResultFound as exc:
            raise exceptions.ObjectNotFound(
                f"{ownername}/{coprname} copr doesn't exist") from exc

    @classmethod
    def get_by_ownername_and_dirname(cls, ownername, dirname):
        """
        Return a Copr object given by OWNERNAME (either '@groupname' or
        'username') and copr DIRNAME (e.g. 'copr-dev:pr:11').
        """
        coprname = CoprDirsLogic.copr_name_from_dirname(dirname)
        return cls.get_by_ownername_coprname(ownername, coprname)

    @classmethod
    def filter_without_ids(cls, query, ids):
        return query.filter(models.Copr.id.notin_(ids))

    @classmethod
    def join_builds(cls, query):
        return (query.outerjoin(models.Copr.builds)
                .options(db.contains_eager(models.Copr.builds))
                .order_by(models.Build.submitted_on.desc()))

    @classmethod
    def join_mock_chroots(cls, query):
        return (query.outerjoin(*models.Copr.mock_chroots.attr)
                .options(db.contains_eager(*models.Copr.mock_chroots.attr))
                .order_by(models.MockChroot.os_release.asc())
                .order_by(models.MockChroot.os_version.asc())
                .order_by(models.MockChroot.arch.asc()))

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
    def get_multiple_fulltext(cls, fulltext=None, projectname=None,
                              ownername=None, packagename=None):

        if fulltext and "/" in fulltext:
            ownername, projectname = helpers.parse_fullname(fulltext)
            fulltext = None

        query = (models.Copr.query.order_by(desc(models.Copr.created_on))
                 .filter(models.Copr.deleted == False))

        if projectname:
            value = "%{}%".format(projectname)
            query = query.filter(models.Copr.name.ilike(value))

        if ownername and ownername[0] != "@":
            query = query.join(models.User)
            value = "%{}%".format(ownername)
            query = query.filter(models.User.username.ilike(value))

        if ownername and ownername[0] == "@":
            query = query.join(models.Group)
            value = "%{}%".format(ownername[1:])
            query = query.filter(models.Group.name.ilike(value))

        if packagename:
            query = query.join(models.Package)
            value = "%{}%".format(packagename)
            query = query.filter(models.Package.name.ilike(value))

        if fulltext:
            query = query.whooshee_search(
                fulltext, whoosheer=CoprWhoosheer, order_by_relevance=100)

        return query

    @classmethod
    def add(cls, user, name, selected_chroots, repos=None, description=None,
            instructions=None, check_for_duplicates=False, group=None, persistent=False,
            auto_prune=True, bootstrap=None, follow_fedora_branching=False, isolation=None,
            appstream=True, **kwargs):

        if not flask.g.user.admin and flask.g.user != user:
            msg = ("You were authorized as '{0}' user without permissions to access "
                   "projects of user '{1}'".format(flask.g.user.name, user.name))
            raise exceptions.AccessRestricted(msg)

        if not flask.g.user.admin and persistent:
            raise exceptions.NonAdminCannotCreatePersistentProject()

        if not flask.g.user.admin and not auto_prune:
            raise exceptions.NonAdminCannotDisableAutoPrunning()

        # form validation checks for duplicates
        cls.new(user, name, group, check_for_duplicates=check_for_duplicates)

        copr = models.Copr(name=name,
                           repos=repos or u"",
                           user=user,
                           description=description or u"",
                           instructions=instructions or u"",
                           created_on=int(time.time()),
                           persistent=persistent,
                           auto_prune=auto_prune,
                           bootstrap=bootstrap,
                           isolation=isolation,
                           follow_fedora_branching=follow_fedora_branching,
                           appstream=appstream,
                           **kwargs)


        if group is not None:
            users_logic.UsersLogic.raise_if_not_in_group(user, group)
            copr.group = group

        copr_dir = models.CoprDir(
            main=True,
            name=name,
            copr=copr)

        db.session.add(copr_dir)
        db.session.add(copr)

        CoprChrootsLogic.new_from_names(
            copr, selected_chroots)

        db.session.flush()
        ActionsLogic.send_create_gpg_key(copr)

        return copr

    @classmethod
    def new(cls, user, copr_name, group=None, check_for_duplicates=True):
        if check_for_duplicates:
            if group is None and cls.exists_for_user(user, copr_name).all():
                raise exceptions.DuplicateException(
                    "Copr: '{0}/{1}' already exists".format(user.name, copr_name))
            elif group:
                if cls.exists_for_group(group, copr_name).all():
                    db.session.rollback()
                    raise exceptions.DuplicateException(
                        "Copr: '@{0}/{1}' already exists".format(group.name, copr_name))

    @classmethod
    def update(cls, user, copr):
        # we should call get_history before other requests, otherwise
        # the changes would be forgotten
        if get_history(copr, "name").has_changes():
            raise MalformedArgumentException("Change name of the project is forbidden")

        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr, "Only owners and admins may update their projects.")

        if not user.admin and not copr.auto_prune:
            raise exceptions.NonAdminCannotDisableAutoPrunning()

        if helpers.being_server_admin(user, copr):
            app.logger.info("Admin '%s' using their permissions to update "
                            "project '%s' settings", user.name, copr.full_name)

        db.session.add(copr)

    @classmethod
    def delete_unsafe(cls, user, copr):
        """
        Deletes copr without termination of ongoing builds.
        """
        cls.raise_if_cant_delete(user, copr)
        # TODO: do we want to dump the information somewhere, so that we can
        # search it in future?
        cls.raise_if_unfinished_blocking_action(
            copr, "Can't delete this project,"
                  " another operation is in progress: {action}")

        ActionsLogic.send_delete_copr(copr)
        CoprDirsLogic.delete_all_by_copr(copr)

        copr.deleted = True
        return copr

    @classmethod
    def exists_for_user(cls, user, coprname, incl_deleted=False):
        existing = (models.Copr.query
                    .order_by(desc(models.Copr.created_on))
                    .filter(models.Copr.name == coprname)
                    .filter(models.Copr.user_id == user.id))

        if not incl_deleted:
            existing = existing.filter(models.Copr.deleted == False)

        return cls.filter_without_group_projects(existing)

    @classmethod
    def exists_for_group(cls, group, coprname, incl_deleted=False):
        existing = (models.Copr.query
                    .order_by(desc(models.Copr.created_on))
                    .filter(models.Copr.name == coprname)
                    .filter(models.Copr.group_id == group.id))

        if not incl_deleted:
            existing = existing.filter(models.Copr.deleted == False)

        return existing

    @classmethod
    def unfinished_blocking_actions_for(cls, copr):
        blocking_actions = [ActionTypeEnum("delete")]

        actions = (models.Action.query
                   .filter(models.Action.object_type == "copr")
                   .filter(models.Action.object_id == copr.id)
                   .filter(models.Action.result ==
                           BackendResultEnum("waiting"))
                   .filter(models.Action.action_type.in_(blocking_actions)))

        return actions

    @classmethod
    def get_yum_repos(cls, copr, empty=False):
        repos = {}
        release_tmpl = "{chroot.os_release}-{chroot.os_version}-{chroot.arch}"
        build = models.Build.query.filter(models.Build.copr_id == copr.id).first()
        if build or empty:
            for chroot in copr.active_chroots:
                release = release_tmpl.format(chroot=chroot)
                repos[release] = fix_protocol_for_backend(
                    os.path.join(copr.repo_url, release + '/'))
        return repos

    @classmethod
    def raise_if_unfinished_blocking_action(cls, copr, message):
        """
        Raise ActionInProgressException if given copr has an unfinished
        action. Return None otherwise.
        """

        unfinished_actions = cls.unfinished_blocking_actions_for(copr).all()
        if unfinished_actions:
            raise exceptions.ActionInProgressException(
                message, unfinished_actions[0])

    @classmethod
    def raise_if_cant_delete(cls, user, copr):
        """
        Raise InsufficientRightsException if given copr cant be deleted
        by given user. Return None otherwise.
        """
        if user.admin:
            return

        if copr.group:
            return users_logic.UsersLogic.raise_if_not_in_group(user, copr.group)

        if user == copr.user:
            return

        raise exceptions.InsufficientRightsException(
            "Only owners may delete their projects.")

    @classmethod
    def raise_if_packit_forge_project_cant_build_in_copr(cls, copr, packit_forge_project):
        """
        Raise InsufficientRightsException if given forge project can't build
        in given copr via Packit. Return None otherwise.
        """
        if packit_forge_project and packit_forge_project not in copr.packit_forge_projects_allowed_list:
            raise exceptions.InsufficientRightsException(
                f"Forge project {packit_forge_project} can't build in this Copr via Packit.")


class CoprPermissionsLogic(object):
    @classmethod
    def get(cls, copr, searched_user):
        query = (models.CoprPermission.query
                 .filter(models.CoprPermission.copr == copr)
                 .filter(models.CoprPermission.user == searched_user))

        return query

    @classmethod
    def get_for_copr(cls, copr):
        query = models.CoprPermission.query.filter(
            models.CoprPermission.copr == copr)

        return query

    @classmethod
    def get_admins_for_copr(cls, copr):
        permissions = cls.get_for_copr(copr)
        return [copr.user] + [p.user for p in permissions if p.copr_admin == helpers.PermissionEnum("approved")]

    @classmethod
    def new(cls, copr_permission):
        db.session.add(copr_permission)

    @classmethod
    def update_permissions(cls, user, copr, copr_permission,
                           new_builder, new_admin):

        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr, "Only owners and admins may update"
                        " their projects permissions.")

        app.logger.info("User '%s' authorized permission change for project '%s'"
                        " - The '%s' user is now 'builder=%s', 'admin=%s'",
                        user.name, copr.full_name, copr_permission.user.name,
                        helpers.PermissionEnum(new_builder),
                        helpers.PermissionEnum(new_admin))

        (models.CoprPermission.query
         .filter(models.CoprPermission.copr_id == copr.id)
         .filter(models.CoprPermission.user_id == copr_permission.user_id)
         .update({"copr_builder": new_builder,
                  "copr_admin": new_admin}))

    @classmethod
    def update_permissions_by_applier(cls, user, copr, copr_permission, new_builder, new_admin):
        app.logger.info("User '%s' requests 'builder=%s', 'admin=%s' "
                        "permissions for project '%s'",
                        user.name,
                        helpers.PermissionEnum(new_builder),
                        helpers.PermissionEnum(new_admin),
                        copr.full_name)

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

            cls.new(perm)

    @classmethod
    def delete(cls, copr_permission):
        db.session.delete(copr_permission)

    @classmethod
    def validate_permission(cls, user, copr, permission, state):
        allowed = ['admin', 'builder']
        if permission not in allowed:
            raise BadRequest(
                "invalid permission '{0}', allowed {1}".format(permission,
                    '|'.join(allowed)))

        allowed = helpers.PermissionEnum.vals.keys()
        if state not in allowed:
            raise BadRequest(
                "invalid '{0}' permission state '{1}', "
                "use {2}".format(permission, state, '|'.join(allowed)))

        if user.id == copr.user_id:
            raise BadRequest("user '{0}' is owner of the '{1}' "
                             "project".format(user.name, copr.full_name))

    @classmethod
    def set_permissions(cls, request_user, copr, user, permission, state):
        users_logic.UsersLogic.raise_if_cant_update_copr(
            request_user, copr,
            "only owners and admins may update their projects permissions.")

        cls.validate_permission(user, copr, permission, state)

        app.logger.info("User '%s' authorized permission change for project '%s'"
                        " - The '%s' user is now '%s=%s'",
                        request_user.name, copr.full_name, user.name,
                        permission, state)

        perm_o = models.CoprPermission(user_id=user.id, copr_id=copr.id)
        perm_o = db.session.merge(perm_o)
        old_state = perm_o.get_permission(permission)

        new_state = helpers.PermissionEnum(state)
        perm_o.set_permission(permission, new_state)
        db.session.merge(perm_o)

        return (old_state, new_state) if old_state != new_state else None

    @classmethod
    def request_permission(cls, copr, user, permission, req_bool):
        approved = helpers.PermissionEnum('approved')
        state = None
        if req_bool is True:
            state = 'request'
        elif req_bool is False:
            state = 'nothing'
        else:
            raise BadRequest("invalid '{0}' permission request '{1}', "
                             "expected True or False".format(permission,
                                 req_bool))

        app.logger.info("User '%s' requests '%s=%s' permission for project '%s'",
                        user.name, permission, state, copr.full_name)

        cls.validate_permission(user, copr, permission, state)
        perm_o = models.CoprPermission(user_id=user.id, copr_id=copr.id)
        perm_o = db.session.merge(perm_o)
        old_state = perm_o.get_permission(permission)
        if old_state == approved and state == 'request':
            raise BadRequest("You already are '{0}' in '{1}'".format(
                                 permission, copr.full_name))

        new_state = helpers.PermissionEnum(state)
        perm_o.set_permission(permission, new_state)

        if old_state != new_state:
            return (old_state, new_state)
        return None


class CoprDirsLogic(object):
    @classmethod
    def get_by_copr_safe(cls, copr, dirname):
        """
        Return _query_ for getting CoprDir by Copr and dirname
        """
        return (db.session.query(models.CoprDir)
                .join(models.Copr)
                .filter(models.Copr.id==copr.id)
                .filter(models.CoprDir.name==dirname)).first()

    @classmethod
    def get_by_copr(cls, copr, dirname):
        """
        Return CoprDir instance per given Copr instance and dirname.  Raise
        ObjectNotFound if it doesn't exist.
        """
        coprdir = cls.get_by_copr_safe(copr, dirname)
        if not coprdir:
            raise exceptions.ObjectNotFound(
                "Dirname '{}' doesn't exist in '{}' copr".format(
                    dirname,
                    copr.full_name))
        return coprdir

    @staticmethod
    def _valid_custom_dir_suffix(copr, dirname):
        """
        Allow users to crate :custom: and :pr:<INT> directories
        """
        if dirname.startswith(copr.name+":custom:"):
            return True
        if not dirname.startswith(copr.name+":pr:"):
            return False

        # PRs must end with integers.  These directories have automatic
        # retention policy.
        parts = dirname.split(":")
        if len(parts) != 3:
            return False
        return all([c.isnumeric() for c in parts[2]])

    @classmethod
    def get_or_create(cls, copr, dirname, trusted_caller=False):
        """
        Create a CoprDir on-demand, e.g. before pull-request builds is
        submitted.  We don't create the "main" CoprDirs here (those are created
        when a new project is created.
        """
        copr_dir = cls.get_by_copr_safe(copr, dirname)
        if copr_dir:
            return copr_dir

        if not dirname.startswith(copr.name+':'):
            raise MalformedArgumentException(
                "Copr dirname must start with '{}:' prefix".format(
                copr.name,
            ))

        if not trusted_caller and not cls._valid_custom_dir_suffix(copr, dirname):
            raise exceptions.BadRequest(
                f"Please use directory format {copr.name}:custom:<SUFFIX_OF_CHOICE> "
                f"or {copr.name}:pr:<ID> (for automatically removed directories)"
            )

        if not all(x.isalnum() for x in dirname.split(":")[1:]):
            raise exceptions.BadRequest(
                f"Wrong directory '{dirname}' specified.  Directory name can "
                "consist of alpha-numeric strings separated by colons.")

        copr_dir = models.CoprDir(name=dirname, copr=copr, main=False)
        ActionsLogic.send_createrepo(copr, dirnames=[dirname])
        db.session.add(copr_dir)
        return copr_dir


    @classmethod
    def get_by_ownername(cls, ownername, dirname):
        return (db.session.query(models.CoprDir)
                .filter(models.CoprDir.name==dirname)
                .filter(models.CoprDir.ownername==ownername))

    @classmethod
    def delete(cls, copr_dir):
        db.session.delete(copr_dir)

    @classmethod
    def delete_with_builds(cls, copr_dir):
        """
        Delete CoprDir istance from database, and transitively delete all
        assigned Builds and BuildChroots.  No Backend action is generated.
        """
        models.Build.query.filter(models.Build.copr_dir_id==copr_dir.id)\
                .delete()
        cls.delete(copr_dir)

    @classmethod
    def delete_all_by_copr(cls, copr):
        for copr_dir in copr.dirs:
            db.session.delete(copr_dir)

    @staticmethod
    def _compare_dir_pairs(pair1, pair2):
        """
        Compare list of pairs from get_all_with_latest_submitted_build_query
        """

        dirname1 = pair1.CoprDir.name
        dirname2 = pair2.CoprDir.name

        if ':' not in dirname1:
            return -1
        if ':' not in dirname2:
            return 1

        pr = False
        for left, right in zip_longest(dirname1.split(':'), dirname2.split(':')):
            if None in [left, right]:
                return 1 if left is None else -1
            if pr:
                try:
                    # _try_ to compare as numbers now
                    return int(right) - int(left)
                except ValueError:
                    # let's fallback to string comparison
                    pr = False
            rc = locale.strcoll(left, right)
            if rc != 0:
                return rc

            # go down to another field
            if left == 'pr':
                pr = True
        return 0

    @classmethod
    def get_all_with_latest_submitted_build_query(cls, copr_id):
        """
        Get query returning list of pairs (CoprDir, latest_build_submitted_on)
        """
        subquery = (
            db.session.query(
                models.Build.submitted_on
            )
            .filter(models.Build.copr_dir_id==models.CoprDir.id)
            .order_by(desc(models.Build.id))
            .limit(1)
            .label("latest_build_submitted_on")
        )
        return (
            db.session.query(models.CoprDir, subquery)
            .filter(models.CoprDir.copr_id==int(copr_id))
        )

    @classmethod
    def get_all_with_latest_submitted_build(cls, copr_id):
        """
        Return a list of pairs like [(CoprDir, latest_build_submitted_on), ...]
        ordered by name.
        """

        keep_days = app.config["KEEP_PR_DIRS_DAYS"]
        now = time.time()

        pairs = list(cls.get_all_with_latest_submitted_build_query(copr_id))

        results = []
        for pair in sorted(pairs, key=cmp_to_key(cls._compare_dir_pairs)):
            last = pair.latest_build_submitted_on
            copr_dir = pair.CoprDir

            removal_candidate = True
            if ':pr:' not in copr_dir.name:
                removal_candidate = False
                delete = False  # never ever remove this!
                remaining_days = 'infinity'
                days_since_last = 0

            elif last is None:
                delete = True
                remaining_days = 0
                days_since_last = float('inf')

            else:
                seconds_since_last = now - last
                days_since_last = seconds_since_last/3600/24
                delete = days_since_last > keep_days
                remaining_days = int(keep_days - days_since_last)
                if remaining_days < 0:
                    remaining_days = 0

            results += [{
                'copr_dir': copr_dir,
                'warn': days_since_last > keep_days / 2,
                'delete': delete,
                'remaining_days': remaining_days,
                'removal_candidate': removal_candidate,
            }]

        return results

    @classmethod
    def get_copr_ids_with_pr_dirs(cls):
        """
        Get query returning all Copr instances that have some PR directories
        """
        return (
            db.session.query(models.CoprDir.copr_id)
            .filter(models.CoprDir.name.like("%:pr:%"))
            .group_by(models.CoprDir.copr_id)
        )

    @classmethod
    def send_delete_dirs_action(cls):
        """
        Go through all projects, and check if there are some PR directories to
        be removed.  Generate delete action for them, and drop them.
        """
        copr_ids = cls.get_copr_ids_with_pr_dirs().all()

        remove_dirs = []
        for copr_id in copr_ids:
            copr_id = copr_id[0]
            all_dirs = cls.get_all_with_latest_submitted_build(copr_id)
            for copr_dir in all_dirs:
                dir_object = copr_dir["copr_dir"]
                if not copr_dir['delete']:
                    continue

                dirname = "{}/{}".format(
                    dir_object.copr.owner_name,
                    dir_object.name,
                )
                print("{} is going to be deleted".format(dirname))
                cls.delete_with_builds(dir_object)
                remove_dirs.append(dirname)

        action = models.Action(
            action_type=ActionTypeEnum("remove_dirs"),
            object_type="copr",
            data=json.dumps(remove_dirs),
            created_on=int(time.time()))

        db.session.add(action)

    @classmethod
    def copr_name_from_dirname(cls, dirname):
        """
        Convert copr dirname (like "foo:pr:1234") to copr name, like "foo"
        without any additional checking.
        """
        parts = dirname.split(":")
        assert len(parts) >= 1
        return parts[0]


@listens_for(models.Copr.auto_createrepo, 'set')
def on_auto_createrepo_change(target_copr, value_acr, old_value_acr, initiator):
    """ Emit createrepo action when auto_createrepo re-enabled"""
    if old_value_acr in [NEVER_SET, NO_VALUE]:
        # Created a new copr.  We handle the createrepo actions within
        # CoprsLogic.add() and the CoprChrootsLogic.new_from_names() called
        # inside.
        return

    if old_value_acr == value_acr:
        # no change
        return

    ActionsLogic.send_createrepo(target_copr, devel=not value_acr)


class BranchesLogic(object):
    @classmethod
    def get_or_create(cls, name, session=None):
        if not session:
            session = db.session
        item = session.query(models.DistGitBranch).filter_by(name=name).first()
        if item:
            return item

        branch = models.DistGitBranch()
        branch.name = name
        session.add(branch)
        return branch


class CoprChrootsLogic(object):
    @classmethod
    def get_multiple(cls, include_deleted=False):
        query = models.CoprChroot.query.join(models.Copr)
        if not include_deleted:
            query = query.filter(models.Copr.deleted.is_(False))
        return query

    @classmethod
    def mock_chroots_from_names(cls, names):
        """
        Return a list of MockChroot objects (not a query object!) which are
        named by one of the ``names`` list.
        """
        # TODO: this should be moved to MockChrootsLogic
        db_chroots = models.MockChroot.query.all()
        mock_chroots = []
        for ch in db_chroots:
            if ch.name in names:
                mock_chroots.append(ch)

        return mock_chroots

    @classmethod
    def get_by_mock_chroot_id(cls, copr, mock_chroot_id):
        """
        Query CoprChroot(s) in Copr with MockChroot.id
        """
        return (
            models.CoprChroot.query
            .filter(models.CoprChroot.copr_id == copr.id)
            .filter(models.CoprChroot.mock_chroot_id == mock_chroot_id)
        )

    @classmethod
    def get_by_name(cls, copr, chroot_name, active_only=True):
        mc = MockChrootsLogic.get_from_name(chroot_name, active_only=active_only).one()
        return cls.get_by_mock_chroot_id(copr, mc.id)

    @classmethod
    def get_by_name_safe(cls, copr, chroot_name):
        """
        :rtype: models.CoprChroot
        """
        try:
            return cls.get_by_name(copr, chroot_name).one()
        except NoResultFound:
            return None

    @classmethod
    def new(cls, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def new_from_names(cls, copr, names):
        for mock_chroot in cls.mock_chroots_from_names(names):
            db.session.add(
                models.CoprChroot(copr=copr, mock_chroot=mock_chroot))

        ActionsLogic.send_createrepo(copr, priority=ActionPriorityEnum("highest"))

    @classmethod
    def create_chroot(cls, user, copr, mock_chroot, buildroot_pkgs=None, repos=None, comps=None, comps_name=None,
                      with_opts="", without_opts="",
                      delete_after=None, delete_notify=None, module_toggle="",
                      bootstrap=None, bootstrap_image=None, isolation=None):
        """
        :type user: models.User
        :type mock_chroot: models.MockChroot
        """
        if buildroot_pkgs is None:
            buildroot_pkgs = ""
        if repos is None:
            repos = ""
        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr,
            "Only owners and admins may update their projects.")

        chroot = models.CoprChroot(copr=copr, mock_chroot=mock_chroot)
        cls._update_chroot(buildroot_pkgs, repos, comps, comps_name, chroot,
                           with_opts, without_opts, delete_after, delete_notify,
                           module_toggle, bootstrap, bootstrap_image, isolation)

        # reassign old build_chroots, if the chroot is re-created
        get_old = logic.builds_logic.BuildChrootsLogic.by_copr_and_mock_chroot
        for old_bch in get_old(copr, mock_chroot):
            old_bch.copr_chroot = chroot

        return chroot

    @classmethod
    def create_chroot_from(cls, from_copr_chroot, copr=None, mock_chroot=None):
        """
        Create a new CoprChroot object for USER, COPR and MOCK_CHROOT,
        inheriting the configuration from FROM_COPR_CHROOT.
        """
        assert copr or mock_chroot
        copr_chroot = clone_sqlalchemy_instance(from_copr_chroot, ["build_chroots"])
        if mock_chroot is not None:
            copr_chroot.mock_chroot = mock_chroot
        if copr is not None:
            copr_chroot.copr = copr
        db.session.add(copr_chroot)
        if copr_chroot.comps_name is not None:
            ActionsLogic.send_update_comps(copr_chroot)
        return copr_chroot

    @classmethod
    def update_chroot(cls, user, copr_chroot, buildroot_pkgs=None, repos=None, comps=None, comps_name=None,
                      with_opts="", without_opts="", delete_after=None, delete_notify=None, module_toggle="",
                      bootstrap=None, bootstrap_image=None, isolation=None):
        """
        :type user: models.User
        :type copr_chroot: models.CoprChroot
        """
        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr_chroot.copr,
            "Only owners and admins may update their projects.")

        if helpers.being_server_admin(user, copr_chroot.copr):
            app.logger.info("Admin '%s' using their permissions to update "
                            "chroot '%s'", user.name, copr_chroot.full_name)

        cls._update_chroot(buildroot_pkgs, repos, comps, comps_name,
                           copr_chroot, with_opts, without_opts, delete_after, delete_notify, module_toggle,
                           bootstrap, bootstrap_image, isolation)
        return copr_chroot

    @classmethod
    def _update_chroot(cls, buildroot_pkgs, repos, comps, comps_name,
                       copr_chroot, with_opts, without_opts, delete_after, delete_notify, module_toggle,
                       bootstrap, bootstrap_image, isolation):
        if buildroot_pkgs is not None:
            copr_chroot.buildroot_pkgs = buildroot_pkgs

        if repos is not None:
            copr_chroot.repos = repos.replace("\n", " ")

        if with_opts is not None:
            copr_chroot.with_opts = with_opts

        if without_opts is not None:
            copr_chroot.without_opts = without_opts

        if comps_name is not None:
            copr_chroot.update_comps(comps)
            copr_chroot.comps_name = comps_name
            ActionsLogic.send_update_comps(copr_chroot)

        if delete_after is not None:
            copr_chroot.delete_after = delete_after

        if delete_notify is not None:
            copr_chroot.delete_notify = delete_notify

        if module_toggle is not None:
            copr_chroot.module_toggle = module_toggle

        if bootstrap is not None:
            copr_chroot.bootstrap = bootstrap

        if isolation is not None:
            copr_chroot.isolation = isolation

        if bootstrap_image is not None:
            # By CLI/API we can set custom_image, and keep bootstrap unset.  In
            # such case set also bootstrap to correct value.
            if not bootstrap:
                copr_chroot.bootstrap = 'custom_image'
            copr_chroot.bootstrap_image = bootstrap_image

        db.session.add(copr_chroot)

    @classmethod
    def update_from_names(cls, user, copr, names):
        """
        Update list of CoprChroots assigned to ``copr`` from chroot ``names``
        array.  The chroots not present in ``names`` are disabled.

        :param user: The user who does the change.
        :type user: models.User
        """

        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr,
            "Only owners and admins may update their projects.")

        # Beware that `current_copr_chroots` contains also unclicked (deleted)
        # chroots. We need them in order to not trying to create a new row when
        # re-enabling chroots but rather settings `deleted` attribute to `False`
        current_copr_chroots = copr.copr_chroots
        chroot_map = {cch.mock_chroot: cch for cch in current_copr_chroots}
        new_mock_chroots = cls.mock_chroots_from_names(names)

        # add non-existing
        run_createrepo_in = set()

        # Iterate through all mock chroots that we have to have enabled.
        for mock_chroot in new_mock_chroots:

            # load the corresponding copr_chroot (if exists)
            copr_chroot = chroot_map.get(mock_chroot)

            if copr_chroot and not copr_chroot.deleted:
                # This chroot exists, and is enabled (not deleted).  No need to
                # touch this one!
                continue

            if not copr_chroot:
                # This chroot is being enabled for the first time, new instance.
                copr_chroot = CoprChrootsLogic.create_chroot(
                    user=user,
                    copr=copr,
                    mock_chroot=mock_chroot,
                )
                db.session.add(copr_chroot)

            # Run the createrepo for this MockChroot for all the assigned
            # CoprDirs.  Note that we do this every-time, even for the
            # chroots that are being re-enabled; even though it might seem to be
            # unnecessary.  For the main CoprDir in the project, it is indeed
            # redundant createrepo run (metadata already exist from the time it
            # was enabled before) but the other existing CoprDirs (for pull
            # requests, e.g.) could be created at the time this CoprChroot was
            # disabled in project, and thus there are likely no metadata for
            # this MockChroot yet.
            run_createrepo_in.add(mock_chroot.name)

            # Make sure it is (re-)enabled.
            copr_chroot.deleted = False
            copr_chroot.delete_after = None

        if run_createrepo_in:
            ActionsLogic.send_createrepo(copr, chroots=list(run_createrepo_in))

        to_remove = []
        for mock_chroot in chroot_map:
            if mock_chroot in new_mock_chroots:
                continue
            if not mock_chroot.is_active:
                # we don't remove EOLed variants here
                continue
            # can't delete here, it would change current_chroots and break
            # iteration
            to_remove.append(mock_chroot)

        shortened = False
        running_builds = set()
        for mc in to_remove:
            # We don't overwhelm  the user with too many build IDs in
            # the error message.
            max_items = 5
            copr_chroot = chroot_map[mc]
            query = CoprChrootsLogic.unfinished_buildchroot(copr_chroot).limit(
                max_items + 1)
            for bch in query:
                if len(running_builds) >= max_items:
                    shortened = True
                    break
                running_builds.add(bch.build_id)
            cls.remove_copr_chroot(flask.g.user, chroot_map[mc])


        # reject the request when some build_chroots are not yet finished
        if running_builds:
            builds = list(running_builds)
            if shortened:
                builds.append("others")
            raise exceptions.ConflictingRequest(
                "Can't drop chroot from project, related "
                "{} still in progress".format(
                    helpers.pluralize("build", builds, be_suffix=True)))


    @classmethod
    def remove_comps(cls, user, copr_chroot):
        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr_chroot.copr,
            "Only owners and admins may update their projects.")

        copr_chroot.comps_name = None
        copr_chroot.comps_zlib = None
        ActionsLogic.send_update_comps(copr_chroot)
        db.session.add(copr_chroot)

    @classmethod
    def remove_copr_chroot(cls, user, copr_chroot):
        """
        :param models.CoprChroot chroot:
        """
        users_logic.UsersLogic.raise_if_cant_update_copr(
            user, copr_chroot.copr,
            "Only owners and admins may update their projects.")

        # If the chroot is already unclicked (deleted), do nothing. We don't
        # want to re-delete the chroot again, and with it, prolong its
        # `delete_after` value.
        if copr_chroot.deleted:
            return

        delete_after = datetime.datetime.now() + datetime.timedelta(days=7)
        copr_chroot.delete_after = delete_after
        copr_chroot.deleted = True

    @classmethod
    def filter_outdated(cls, query):
        """
        Filter query to fetch only `CoprChroot` instances that are EOL but still
        in the data preservation period
        """
        return (query.filter(models.CoprChroot.delete_after
                             >= datetime.datetime.now())
                     # Filter only such chroots that are not unclicked (deleted)
                     # from a project. We don't want the EOL machinery for them,
                     # they are deleted.
                     .filter(models.CoprChroot.deleted.isnot(True))

                     # Filter only inactive (i.e. EOL) chroots
                     .filter(not_(models.MockChroot.is_active)))


    @classmethod
    def should_already_be_noticed(cls, remaining_days):
        """
        In issue#1724 we realized that we did not notify some chroots.  This
        method is here temporarily to fix the situation.  We give such chroots
        a bit more time so there's a chance we'll notify the maintainers.
        """
        exp_delete_after = datetime.datetime.now() \
                         + datetime.timedelta(days=remaining_days)

        query = cls.get_multiple()
        return (
            query.filter(models.CoprChroot.delete_after
                         < exp_delete_after)
             # Filter-out manually deleted chroots.
             .filter(models.CoprChroot.deleted.isnot(True))
             # We want not-yet notified chroots.
             .filter(models.CoprChroot.delete_notify.is_(None))
             # Filter only inactive (i.e. EOL) chroots
             .filter(not_(models.MockChroot.is_active))
        )

    @classmethod
    def filter_to_be_deleted(cls, query):
        """
        Filter query to fetch only `CoprChroot` instances whose data on backend
        should be deleted for some reason:

        1) They were unclicked from the project settings and the short
           preservation time is over
        2) They are EOL and nobody prolonged their preservation
        """
        return query.filter(models.CoprChroot.delete_after
                            < datetime.datetime.now())

    @classmethod
    def unfinished_buildchroot(cls, copr_chroot):
        """
        Query returning list of unfinished BuildChroots assigned to
        the given CoprChroot.
        """
        statuses = helpers.FINISHED_STATUSES
        return (
            models.BuildChroot.query
            .filter(models.BuildChroot.copr_chroot==copr_chroot)
            .filter(not_(models.BuildChroot.status.in_(statuses)))
        )

class CoprScoreLogic:
    """
    Class for logic regarding upvoting and downvoting projects
    """

    @classmethod
    def get(cls, copr, user):
        query = db.session.query(models.CoprScore)
        query = query.filter(models.CoprScore.copr_id == copr.id)
        query = query.filter(models.CoprScore.user_id == user.id)
        return query

    @classmethod
    def upvote(cls, copr):
        return cls.vote(copr, 1)

    @classmethod
    def downvote(cls, copr):
        return cls.vote(copr, -1)

    @classmethod
    def vote(cls, copr, value):
        """
        Low-level function for giving score to projects. The `value` should be
        a negative number for downvoting or a positive number for upvoting.
        """
        score = models.CoprScore(copr_id=copr.id, user_id=flask.g.user.id,
                                 score=(1 if value > 0 else -1))
        db.session.add(score)
        return score

    @classmethod
    def reset(cls, copr):
        cls.get(copr, flask.g.user).delete()

    @classmethod
    def get_popular_projects(cls, limit=10):
        """
        Get projects with the highest score (upvotes/downvotes feature).
        The result is returned as tuples Copr.id and its score, but may be
        changed to return tuples of Copr object and its score in the future
        """
        query = db.session.query(
            models.CoprScore.copr_id,
            func.sum(models.CoprScore.score).label("score_sum")
        )
        return (query.group_by(models.CoprScore.copr_id)
                .order_by(desc("score_sum"))
                .limit(limit))


class MockChrootsLogic(object):
    @classmethod
    def get(cls, os_release, os_version, arch, active_only=False, noarch=False):
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

        name_tuple = cls.tuple_from_name(chroot_name, noarch=noarch)
        return cls.get(name_tuple[0], name_tuple[1], name_tuple[2],
                       active_only=active_only, noarch=noarch)

    @classmethod
    def get_multiple(cls, active_only=False):
        query = models.MockChroot.query
        if active_only:
            query = query.filter(models.MockChroot.is_active == True)
        return query

    @classmethod
    def add(cls, name):
        name_tuple = cls.tuple_from_name(name)
        if cls.get(*name_tuple).first():
            raise exceptions.DuplicateException(
                "Mock chroot with this name already exists.")
        new_chroot = models.MockChroot(os_release=name_tuple[0],
                                       os_version=name_tuple[1],
                                       arch=name_tuple[2])
        cls.new(new_chroot)
        return new_chroot

    @classmethod
    def active_names(cls):
        return [ch.name for ch in cls.get_multiple(active_only=True).all()]

    @classmethod
    def active_names_with_comments(cls):
        return [(ch.name, ch.comment) for ch in cls.get_multiple(active_only=True).all()]

    @classmethod
    def new(cls, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def edit_by_name(cls, name, is_active):
        """
        Set the "MockChroot.active" status from 'is_active'.  When re-activating
        (we occasionally disable some chroots temporarily) we need to re-set the
        'final_prunerepo_done' otherwise it would never be cleaned up in the
        future.
        """
        name_tuple = cls.tuple_from_name(name)
        mock_chroot = cls.get(*name_tuple).first()
        if not mock_chroot:
            raise exceptions.NotFoundException(
                "Mock chroot with this name doesn't exist.")

        mock_chroot.is_active = is_active
        if is_active:
            mock_chroot.final_prunerepo_done = False
        cls.update(mock_chroot)
        return mock_chroot

    @classmethod
    def update(cls, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def delete_by_name(cls, name):
        name_tuple = cls.tuple_from_name(name)
        mock_chroot = cls.get(*name_tuple).first()
        if not mock_chroot:
            raise exceptions.NotFoundException(
                "Mock chroot with this name doesn't exist.")

        cls.delete(mock_chroot)

    @classmethod
    def delete(cls, mock_chroot):
        db.session.delete(mock_chroot)

    @classmethod
    def tuple_from_name(cls, name, noarch=False):
        """
        Input is either 'NAME-VERSION-ARCH' string or just 'NAME-VERSION',
        depending on the NOARCH input argument.

        Note that to deterministically split the string into tuple using comma
        symbol, we can either allow comma to be part of the OS_NAME or
        OS_VERSION but *not both*.  We somewhat artificially decided to allow
        dashes in name instead of version (i.e. that we interpret the string
        'centos-stream-8-x86_64' as ("centos-stream", "8") instead of
        ("centos", "stream-8").
        """
        split_name = name.rsplit("-", 1) if noarch else name.rsplit("-", 2)

        valid = False
        if noarch and len(split_name) in [2, 3]:
            valid = True
        if not noarch and len(split_name) == 3:
            valid = True

        if not valid:
            raise MalformedArgumentException("Chroot identification is not valid")

        if noarch and len(split_name) == 2:
            split_name.append(None)

        return tuple(split_name)

    @classmethod
    def prunerepo_finished(cls, chroots_pruned):
        for chroot_name in chroots_pruned:
            chroot = cls.get_from_name(chroot_name).one()
            if not chroot.is_active:
                chroot.final_prunerepo_done = True

        db.session.commit()
        return True

    @classmethod
    def chroots_prunerepo_status(cls):
        query = models.MockChroot.query
        chroots = {}
        for chroot in query:
            chroots[chroot.name] = {
                "active": bool(chroot.is_active),
                "final_prunerepo_done": bool(chroot.final_prunerepo_done),
            }

        return chroots


class PinnedCoprsLogic(object):

    @classmethod
    def get_all(cls):
        return db.session.query(models.PinnedCoprs).order_by(models.PinnedCoprs.position)

    @classmethod
    def get_by_id(cls, pin_id):
        return cls.get_all().filter(models.PinnedCoprs.id == pin_id)

    @classmethod
    def get_by_owner(cls, owner):
        if isinstance(owner, models.Group):
            return cls.get_by_group_id(owner.id)
        return cls.get_by_user_id(owner.id)

    @classmethod
    def get_by_user_id(cls, user_id):
        return cls.get_all().filter(models.PinnedCoprs.user_id == user_id)

    @classmethod
    def get_by_group_id(cls, group_id):
        return cls.get_all().filter(models.PinnedCoprs.group_id == group_id)

    @classmethod
    def add(cls, owner, copr_id, position):
        kwargs = dict(copr_id=copr_id, position=position)
        kwargs["group_id" if isinstance(owner, models.Group) else "user_id"] = owner.id
        pin = models.PinnedCoprs(**kwargs)
        db.session.add(pin)

    @classmethod
    def delete_by_owner(cls, owner):
        query = db.session.query(models.PinnedCoprs)
        if isinstance(owner, models.Group):
            return query.filter(models.PinnedCoprs.group_id == owner.id).delete()
        return query.filter(models.PinnedCoprs.user_id == owner.id).delete()

    @classmethod
    def delete_by_copr(cls, copr):
        return (db.session.query(models.PinnedCoprs)
                .filter(models.PinnedCoprs.copr_id == copr.id)
                .delete())
