import time

from coprs import db
from coprs import exceptions
from coprs import models
from coprs import signals

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
            query = query.filter(models.Build.copr == copr)
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
    def get_waiting_builds(cls, user):
        # return builds that aren't both started and finished (if build start submission
        # fails, we still want to mark the build as non-waiting, if it ended)
        # this has very different goal then get_multiple, so implement it alone
        query = models.Build.query.join(models.Build.copr).\
                                   join(models.User).\
                                   options(db.contains_eager(models.Build.copr)).\
                                   options(db.contains_eager('copr.owner')).\
                                   filter(models.Build.started_on == None).\
                                   filter(models.Build.ended_on == None).\
                                   filter(models.Build.canceled != True).\
                                   order_by(models.Build.submitted_on.asc())
        return query

    @classmethod
    def get_by_ids(cls, user, ids):
        return models.Build.query.filter(models.Build.id.in_(ids))

    @classmethod
    def add(cls, user, pkgs, copr):
        build = models.Build(
            pkgs=pkgs,
            copr=copr,
            repos=copr.repos,
            chroots=' '.join(map(
                lambda x: x.chroot_name, copr.mock_chroots)
                ),
            user=user,
            submitted_on=int(time.time()))
        # no need to check for authorization here
        cls.new(user, build, copr, check_authorized=False)
        return build

    @classmethod
    def new(cls, user, build, copr, check_authorized = True):
        if check_authorized:
            if not user.can_build_in(copr):
                raise exceptions.InsufficientRightsException('User {0} cannot build in copr {1}/{2}'.format(user.name, copr.owner.name, copr.name))
        if not build.submitted_on:
            build.submitted_on = int(time.time())
        if not build.user:
            build.user = user

        coprs_logic.CoprsLogic.increment_build_count(user, copr)
        db.session.add(build)

    @classmethod
    def update_state_from_dict(cls, user, build, upd_dict):
        for attr in ['results', 'started_on', 'ended_on', 'status']:
            value = upd_dict.get(attr, None)
            if value != None:
                setattr(build, attr, value)
                if attr == 'ended_on':
                    signals.build_finished.send(cls, build=build)

        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if build.user_id != user.id:
            raise exceptions.InsufficientRightsException('You can only cancel your own builds.')
        build.canceled = True
