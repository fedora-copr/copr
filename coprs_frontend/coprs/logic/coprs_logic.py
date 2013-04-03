import time

from coprs import db
from coprs import exceptions
from coprs import helpers
from coprs import models
from coprs import signals
from coprs import whoosheers
from coprs.logic import users_logic

class CoprsLogic(object):
    """Used for manipulating Coprs. All methods accept user object as a first argument, as this may be needed in future."""

    @classmethod
    def get(cls, user, username, coprname, **kwargs):
        with_builds = kwargs.get('with_builds', False)
        with_mock_chroots = kwargs.get('with_mock_chroots', False)

        query = db.session.query(models.Copr).\
                           join(models.Copr.owner).\
                           options(db.contains_eager(models.Copr.owner)).\
                           filter(models.Copr.name == coprname).\
                           filter(models.User.openid_name == models.User.openidize_name(username)).\
                           filter(models.Copr.deleted==False)

        if with_builds:
            query = query.outerjoin(models.Copr.builds).\
                          options(db.contains_eager(models.Copr.builds)).\
                          order_by(models.Build.submitted_on.desc())
        if with_mock_chroots:
            query = query.outerjoin(*models.Copr.mock_chroots.attr).\
                          options(db.contains_eager(*models.Copr.mock_chroots.attr)).\
                          order_by(models.MockChroot.os_release.asc()).\
                          order_by(models.MockChroot.os_version.asc()).\
                          order_by(models.MockChroot.arch.asc())

        return query

    @classmethod
    def get_multiple(cls, user, **kwargs):
        user_relation = kwargs.get('user_relation', None)
        username = kwargs.get('username', None)
        with_mock_chroots = kwargs.get('with_mock_chroots', None)
        incl_deleted = kwargs.get('incl_deleted', None)
        ids = kwargs.get('ids', None)

        query = db.session.query(models.Copr).\
                           join(models.Copr.owner).\
                           options(db.contains_eager(models.Copr.owner)).\
                           order_by(models.Copr.id.desc())

        if not incl_deleted:
            query = query.filter(models.Copr.deleted==False)

        if isinstance(ids, list): # can be an empty list
            query = query.filter(models.Copr.id.in_(ids))

        if user_relation == 'owned':
            query = query.filter(models.User.openid_name == models.User.openidize_name(username))
        elif user_relation == 'allowed':
            aliased_user = db.aliased(models.User)
            query = query.join(models.CoprPermission, models.Copr.copr_permissions).\
                          filter(models.CoprPermission.copr_builder == helpers.PermissionEnum('approved')).\
                          join(aliased_user, models.CoprPermission.user).\
                          filter(aliased_user.openid_name == models.User.openidize_name(username))
        if with_mock_chroots:
            query = query.outerjoin(*models.Copr.mock_chroots.attr).\
                          options(db.contains_eager(*models.Copr.mock_chroots.attr)).\
                          order_by(models.MockChroot.os_release.asc()).\
                          order_by(models.MockChroot.os_version.asc()).\
                          order_by(models.MockChroot.arch.asc())

        return query

    @classmethod
    def get_multiple_fulltext(cls, user, search_string):
        query = models.Copr.query.join(models.User).\
                                  filter(models.Copr.deleted==False).\
                                  whooshee_search(search_string)
        return query

    @classmethod
    def add(cls, user, name, repos, selected_chroots, description,
        instructions, check_for_duplicates=False):
        copr = models.Copr(name=name,
                           repos=repos,
                           owner=user,
                           description=description,
                           instructions=instructions,
                           created_on=int(time.time()))
        CoprsLogic.new(user, copr,
            check_for_duplicates=check_for_duplicates) # form validation checks for duplicates
        CoprChrootsLogic.new_from_names(user, copr,
            selected_chroots)
        return copr

    @classmethod
    def new(cls, user, copr, check_for_duplicates=True):
        if check_for_duplicates and cls.exists_for_user(user, copr.name).all():
            raise exceptions.DuplicateException(
                'Copr: "{0}" already exists'.format(copr.name))
        signals.copr_created.send(cls, copr=copr)
        db.session.add(copr)

    @classmethod
    def update(cls, user, copr, check_for_duplicates = True):
        cls.raise_if_unfinished_blocking_action(user, copr,
                                       'Can\'t change this Copr name, another operation is in progress: {action}')
        users_logic.UsersLogic.raise_if_cant_update_copr(user, copr,
                                                         'Only owners and admins may update their Coprs.')

        existing = cls.exists_for_user(copr.owner, copr.name).first()
        if existing:
            if check_for_duplicates and existing.id != copr.id:
                raise exceptions.DuplicateException('Copr: "{0}" already exists'.format(copr.name))
        else: # we're renaming
            # if we fire a models.Copr.query, it will use the modified copr in session
            # -> workaround this by just getting the name
            old_copr_name = db.session.query(models.Copr.name).filter(models.Copr.id==copr.id).\
                                                               filter(models.Copr.deleted==False).\
                                                               first()[0]
            action = models.Action(action_type=helpers.ActionTypeEnum('rename'),
                                   object_type='copr',
                                   object_id=copr.id,
                                   old_value='{0}/{1}'.format(copr.owner.name, old_copr_name),
                                   new_value='{0}/{1}'.format(copr.owner.name, copr.name),
                                   created_on=int(time.time()))
            db.session.add(action)
        db.session.add(copr)

    @classmethod
    def delete(cls, user, copr, check_for_duplicates=True):
        cls.raise_if_cant_delete(user, copr)
        # TODO: do we want to dump the information somewhere, so that we can search it in future?
        cls.raise_if_unfinished_blocking_action(user, copr,
                                       'Can\'t delete this Copr, another operation is in progress: {action}')
        action = models.Action(action_type=helpers.ActionTypeEnum('delete'),
                               object_type='copr',
                               object_id=copr.id,
                               old_value='{0}/{1}'.format(copr.owner.name, copr.name),
                               new_value='',
                               created_on=int(time.time()))
        copr.deleted = True

        db.session.add(action)

        return copr

    @classmethod
    def exists_for_user(cls, user, coprname, incl_deleted=False):
        existing = models.Copr.query.filter(models.Copr.name==coprname).\
                                     filter(models.Copr.owner_id==user.id)
        if not incl_deleted:
            existing = existing.filter(models.Copr.deleted==False)

        return existing

    @classmethod
    def increment_build_count(cls, user, copr): # TODO API of this method is different, maybe change?
        models.Copr.query.filter(models.Copr.id == copr.id).\
                          update({models.Copr.build_count: models.Copr.build_count + 1})

    @classmethod
    def unfinished_blocking_actions_for(cls, user, copr):
        blocking_actions = [helpers.ActionTypeEnum('rename'),
                            helpers.ActionTypeEnum('delete')]
        actions = models.Action.query.filter(models.Action.object_type=='copr').\
                                      filter(models.Action.object_id==copr.id).\
                                      filter(models.Action.result==helpers.BackendResultEnum('waiting')).\
                                      filter(models.Action.action_type.in_(blocking_actions))

        return actions

    @classmethod
    def raise_if_unfinished_blocking_action(cls, user, copr, message):
        """This method raises ActionInProgressException if given copr has an unfinished
        action. Returns None otherwise.
        """
        unfinished_actions = cls.unfinished_blocking_actions_for(user, copr).all()
        if unfinished_actions:
            raise exceptions.ActionInProgressException(message, unfinished_actions[0])

    @classmethod
    def raise_if_cant_delete(cls, user, copr):
        """This method raises InsufficientRightsException if given copr cant be deleted
        by given user. Returns None otherwise.
        """
        if not user.admin and user != copr.owner:
            raise exceptions.InsufficientRightsException('Only owners may delete their Coprs.')

class CoprPermissionsLogic(object):
    @classmethod
    def get(cls, user, copr, searched_user):
        query = models.CoprPermission.query.filter(models.CoprPermission.copr == copr).\
                                            filter(models.CoprPermission.user == searched_user)

        return query

    @classmethod
    def get_for_copr(cls, user, copr):
        query = models.CoprPermission.query.filter(models.CoprPermission.copr == copr)

        return query

    @classmethod
    def new(cls, user, copr_permission):
        db.session.add(copr_permission)

    @classmethod
    def update_permissions(cls, user, copr, copr_permission, new_builder, new_admin):
        users_logic.UsersLogic.raise_if_cant_update_copr(user, copr,
                                                         'Only owners and admins may update their Coprs permissions.')
        models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).\
                                    filter(models.CoprPermission.user_id == copr_permission.user_id).\
                                    update({'copr_builder': new_builder,
                                            'copr_admin': new_admin})

    @classmethod
    def update_permissions_by_applier(cls, user, copr, copr_permission, new_builder, new_admin):
        if copr_permission:
            # preserve approved permissions if set
            if not new_builder or copr_permission.copr_builder != helpers.PermissionEnum('approved'):
                copr_permission.copr_builder = new_builder
            if not new_admin or copr_permission.copr_admin != helpers.PermissionEnum('approved'):
                copr_permission.copr_admin = new_admin
        else:
            perm = models.CoprPermission(user = user, copr = copr, copr_builder = new_builder, copr_admin = new_admin)
            cls.new(user, perm)

    @classmethod
    def delete(cls, user, copr_permission):
        db.session.delete(copr_permission)

class CoprChrootsLogic(object):
    @classmethod
    def mock_chroots_from_names(cls, user, names):
        db_chroots = models.MockChroot.query.all()
        mock_chroots = []
        for ch in db_chroots:
            if ch.chroot_name in names:
                mock_chroots.append(ch)

        return mock_chroots

    @classmethod
    def new(cls, user, mock_chroot):
        db.session.add(mock_chroot)

    @classmethod
    def new_from_names(cls, user, copr, names):
        for mock_chroot in cls.mock_chroots_from_names(user, names):
            db.session.add(models.CoprChroot(copr=copr, mock_chroot=mock_chroot))

    @classmethod
    def update_from_names(cls, user, copr, names):
        current_chroots = copr.mock_chroots
        new_chroots = cls.mock_chroots_from_names(user, names)
        # add non-existing
        for mock_chroot in new_chroots:
            if mock_chroot not in current_chroots:
                db.session.add(models.CoprChroot(copr=copr, mock_chroot=mock_chroot))

        # delete no more present
        to_remove = []
        for mock_chroot in current_chroots:
            if mock_chroot not in new_chroots:
                # can't delete here, it would change current_chroots and break iteration
                to_remove.append(mock_chroot)

        for mc in to_remove:
            copr.mock_chroots.remove(mc)

class MockChrootsLogic(object):
    @classmethod
    def get(cls, user, os_release, os_version, arch, active_only = False):
        return models.MockChroot.query.filter(models.MockChroot.os_release==os_release,
                                              models.MockChroot.os_version==os_version,
                                              models.MockChroot.arch==arch)

    @classmethod
    def get_multiple(cls, user, active_only=False):
        query = models.MockChroot.query
        if active_only:
            query = query.filter(models.MockChroot.is_active==True)
        return query

    @classmethod
    def add(cls, user, name):
        name_tuple = cls.tuple_from_name(user, name)
        if cls.get(user, *name_tuple).first():
            raise exceptions.DuplicateException('Mock chroot with this name already exists.')
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
            raise exceptions.NotFoundException('Mock chroot with this name doesn\'t exist.')

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
            raise exceptions.NotFoundException('Mock chroot with this name doesn\'t exist.')

        cls.delete(user, mock_chroot)

    @classmethod
    def delete(cls, user, mock_chroot):
        db.session.delete(mock_chroot)

    @classmethod
    def tuple_from_name(cls, user, name):
        split_name = name.rsplit('-', 1)
        if len(split_name) < 2:
            raise exceptions.MalformedArgumentException(
                    'Chroot Name doesn\'t contain dash, can\'t determine chroot architecure.')
        if '-' in split_name[0]:
            os_release, os_version = split_name[0].rsplit('-')
        else:
            os_release, os_version = split_name[0], ''

        arch = split_name[1]
        return (os_release, os_version, arch)
