from coprs import db
from coprs import exceptions
from coprs import models

from coprs.logic import coprs_logic

class BuildsLogic(object):
    @classmethod
    def get(cls, user, build_id):
        query = models.Build.query.filter(models.Build.id == build_id)
        return query

    @classmethod
    def get_multiple(cls, user, **kwargs):
        copr = kwargs.get('copr', None)
        username = kwargs.get('username', None)
        coprname = kwargs.get('coprname', None)

        query = models.Build.query.order_by(models.Build.submitted_on.desc())

        # if we get copr, query by its id
        if copr:
            query.filter(models.Build.copr == copr)
        elif username and coprname:
            query = query.join(models.Build.copr).\
                          options(db.contains_eager(models.Build.copr)).\
                          join(models.Copr.owner).\
                          filter(models.Copr.name == coprname).\
                          filter(models.User.openid_name == models.User.openidize_name(username)).\
                          order_by(models.Build.submitted_on.desc())
        else:
            raise exceptions.ArgumentMissingException('Must pass either copr or both coprname and username')

        return query

    @classmethod
    def new(cls, user, build, copr, check_authorized = True):
        if check_authorized:
            if not user.can_build_in(copr):
                raise exceptions.InsufficientRightsException('User {0} cannot build in copr {1}/{2}'.format(user.name, copr.owner.name, copr.name))

        coprs_logic.CoprsLogic.increment_build_count(user, copr)
        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if build.user_id != user.id:
            raise exceptions.InsufficientRightsException('You can only cancel your own builds.')
        build.canceled = True
