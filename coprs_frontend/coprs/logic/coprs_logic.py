import time

from coprs import db
from coprs import exceptions
from coprs import helpers
from coprs import models

class CoprsLogic(object):
    """Used for manipulating Coprs. All methods accept user object as a first argument, as this may be needed in future."""
    @classmethod
    def get(cls, user, username, coprname, **kwargs):
        with_builds = kwargs.get('with_builds', False)

        query = db.session.query(models.Copr).\
                           join(models.Copr.owner).\
                           options(db.contains_eager(models.Copr.owner)).\
                           filter(models.Copr.name == coprname).\
                           filter(models.User.openid_name == models.User.openidize_name(username))

        if with_builds:
            query = query.outerjoin(models.Copr.builds).\
                          options(db.contains_eager(models.Copr.builds)).\
                          order_by(models.Build.submitted_on.desc())

        return query

    @classmethod
    def add_copr(cls, user, name, repos, selected_chroots, description, instructions):
        copr = models.Copr(name=name,
                           repos=repos,
                           owner=user,
                           description=description,
                           instructions=instructions,
                           created_on=int(time.time()))
        CoprsLogic.new(user, copr,
            check_for_duplicates=False) # form validation checks for duplicates
        CoprsChrootLogic.new_from_names(user, copr,
            selected_chroots)
        return copr

    @classmethod
    def get_multiple(cls, user, **kwargs):
        user_relation = kwargs.get('user_relation', None)
        username = kwargs.get('username', None)
        with_mock_chroots = kwargs.get('with_mock_chroots')

        query = db.session.query(models.Copr).\
                           join(models.Copr.owner).\
                           options(db.contains_eager(models.Copr.owner))
        if user_relation == 'owned':
            query = query.filter(models.User.openid_name == models.User.openidize_name(username))
        elif user_relation == 'allowed':
            aliased_user = db.aliased(models.User)
            query = query.join(models.CoprPermission, models.Copr.copr_permissions).\
                          filter(models.CoprPermission.copr_builder == helpers.PermissionEnum.num('approved')).\
                          join(aliased_user, models.CoprPermission.user).\
                          filter(aliased_user.openid_name == models.User.openidize_name(username))
        if with_mock_chroots:
            query = query.outerjoin(*models.Copr.mock_chroots.attr).\
                          options(db.contains_eager(*models.Copr.mock_chroots.attr))
        return query

    @classmethod
    def new(cls, user, copr, check_for_duplicates = True):
        if check_for_duplicates and cls.exists_for_current_user(user, copr.name):
            raise exceptions.DuplicateCoprNameException
        db.session.add(copr)

    @classmethod
    def update(cls, user, copr, check_for_duplicates = True):
        if check_for_duplicates and cls.exists_for_current_user(user, copr.name):
            raise exceptions.DuplicateCoprNameException
        db.session.add(copr)

    @classmethod
    def exists_for_current_user(cls, user, coprname):
        existing = models.Copr.query.filter(models.Copr.name == coprname).\
                                     filter(models.Copr.owner_id == user.id)

        return existing

    @classmethod
    def increment_build_count(cls, user, copr): # TODO API of this method is different, maybe change?
        models.Copr.query.filter(models.Copr.id == copr.id).\
                          update({models.Copr.build_count: models.Copr.build_count + 1})

class CoprsPermissionLogic(object):
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
        models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).\
                                    filter(models.CoprPermission.user_id == copr_permission.user_id).\
                                    update({'copr_builder': new_builder,
                                            'copr_admin': new_admin})

    @classmethod
    def update_permissions_by_applier(cls, user, copr, copr_permission, new_builder, new_admin):
        if copr_permission:
            # preserve approved permissions if set
            if not new_builder or copr_permission.copr_builder != helpers.PermissionEnum.num('approved'):
                copr_permission.copr_builder = new_builder
            if not new_admin or copr_permission.copr_admin != helpers.PermissionEnum.num('approved'):
                copr_permission.copr_admin = new_admin
        else:
            perm = models.CoprPermission(user = user, copr = copr, copr_builder = new_builder, copr_admin = new_admin)
            cls.new(user, perm)

    @classmethod
    def delete(cls, user, copr_permission):
        db.session.delete(copr_permission)

class CoprsChrootLogic(object):
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
        for mock_chroot in current_chroots:
            if mock_chroot not in new_chroots:
                copr.mock_chroots.remove(mock_chroot)
