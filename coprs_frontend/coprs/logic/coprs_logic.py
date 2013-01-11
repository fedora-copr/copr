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
    def get_multiple(cls, user, **kwargs):
        user_relation = kwargs.get('user_relation', None)
        username = kwargs.get('username', None)

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
            copr_permission.copr_builder = new_builder
            copr_permission.copr_admin = new_admin
        else:
            perm = models.CoprPermission(user = user, copr = copr, copr_builder = new_builder, copr_admin = new_admin)
            cls.new(user, perm)

    @classmethod
    def delete(cls, user, copr_permission):
        db.session.delete(copr_permission)
