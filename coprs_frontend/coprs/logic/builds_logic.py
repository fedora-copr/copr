import time

from coprs import db
from coprs import exceptions
from coprs import models
from coprs import signals

from coprs.logic import coprs_logic
from coprs.logic import users_logic

class BuildsLogic(object):
    @classmethod
    def get(cls, build_id):
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
    def get_waiting(cls):
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
    def get_by_ids(cls, ids):
        return models.Build.query.filter(models.Build.id.in_(ids))

    @classmethod
    def add(cls, user, pkgs, copr):
        coprs_logic.CoprsLogic.raise_if_unfinished_blocking_action(user, copr,
                                                          'Can\'t build while there is an operation in progress: {action}')
        users_logic.UsersLogic.raise_if_cant_build_in_copr(user, copr,
                                                           'You don\'t have permissions to build in this copr.')
        build = models.Build(
            pkgs=pkgs,
            copr=copr,
            repos=copr.repos,
            user=user,
            submitted_on=int(time.time()))
        cls.new(user, build, copr)
        return build

    @classmethod
    def new(cls, user, build, copr):
        if not build.submitted_on:
            build.submitted_on = int(time.time())
        if not build.user:
            build.user = user

        coprs_logic.CoprsLogic.increment_build_count(user, copr)
        db.session.add(build)

        # add BuildChroot object for each active chroot
        # this copr is assigned to
        for chroot in copr.active_mock_chroots:
            buildchroot = models.BuildChroot(
                build=build,
                mock_chroot=chroot)

            db.session.add(buildchroot)

    @classmethod
    def update_state_from_dict(cls, build, upd_dict):
        if 'chroot' in upd_dict:
            # update respective chroot status
            for build_chroot in build.build_chroots:
                if build_chroot.mock_chroot.chroot_name == upd_dict['chroot']:
                    build_chroot.status = upd_dict['status']

                    db.session.add(build_chroot)

        for attr in ['results', 'started_on', 'ended_on']:
            value = upd_dict.get(attr, None)
            if value:
                # only update started_on once
                if attr == 'started_on' and build.started_on:
                    continue

                # only update ended_on and results
                # when there are no pending builds
                if (attr in ['ended_on', 'results'] and
                        build.has_pending_chroot):
                    continue

                if attr == 'ended_on':
                    signals.build_finished.send(cls, build=build)

                setattr(build, attr, value)

        db.session.add(build)

    @classmethod
    def cancel_build(cls, user, build):
        if build.user_id != user.id:
            raise exceptions.InsufficientRightsException('You can only cancel your own builds.')
        build.canceled = True
