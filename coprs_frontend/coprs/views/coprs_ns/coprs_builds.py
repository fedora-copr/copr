import flask

from coprs import db
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.logic import builds_logic
from coprs.logic import coprs_logic

from coprs.views.misc import login_required, page_not_found
from coprs.views.coprs_ns import coprs_ns


@coprs_ns.route('/<username>/<coprname>/builds/', defaults={'page': 1})
@coprs_ns.route('/<username>/<coprname>/builds/<int:page>/')
def copr_builds(username, coprname, page=1):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    builds_query = builds_logic.BuildsLogic.get_multiple(flask.g.user, copr=copr)

    paginator = helpers.Paginator(builds_query, copr.build_count, page, per_page_override = 10)
    return flask.render_template('coprs/detail/builds.html', copr=copr, builds=paginator.sliced_query, paginator=paginator)


@coprs_ns.route('/<username>/<coprname>/add_build/')
@login_required
def copr_add_build(username, coprname, form=None):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    if not form:
        form = forms.BuildForm()

    return flask.render_template('coprs/detail/add_build.html', copr=copr, form=form)


@coprs_ns.route('/<username>/<coprname>/new_build/', methods = ["POST"])
@login_required
def copr_new_build(username, coprname):
    form = forms.BuildForm()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    if form.validate_on_submit() and flask.g.user.can_build_in(copr):
        try:
            build = builds_logic.BuildsLogic.add(user=flask.g.user,
                                                 pkgs=form.pkgs.data.replace('\n', ' '),
                                                 copr=copr) # we're checking authorization above for now
            if flask.g.user.proven:
                build.memory_reqs = form.memory_reqs.data
                build.timeout = form.timeout.data
        except exceptions.ActionInProgressException as e:
            flask.flash(str(e))
            db.session.rollback()
        else:
            flask.flash("Build was added")
            db.session.commit()

        return flask.redirect(flask.url_for('coprs_ns.copr_builds', username=username, coprname=copr.name))
    else:
        return copr_add_build(username=username, coprname=coprname, form=form)


@coprs_ns.route('/<username>/<coprname>/cancel_build/<int:build_id>/', methods = ['POST'])
@login_required
def copr_cancel_build(username, coprname, build_id):
    # only the user who ran the build can cancel it
    build = builds_logic.BuildsLogic.get(build_id).first()
    if not build: # hey, this Build doesn't exist
        return page_not_found('Build with id {0} does not exist.'.format(build_id))
    try:
        builds_logic.BuildsLogic.cancel_build(flask.g.user, build)
    except exceptions.InsufficientRightsException as e:
        flask.flash(str(e))
    else:
        db.session.commit()
        flask.flash('Build was canceled')

    return flask.redirect(flask.url_for('coprs_ns.copr_builds', username = username, coprname = coprname))


@coprs_ns.route('/<username>/<coprname>/repeat_build/<int:build_id>/', methods = ['POST'])
@login_required
def copr_repeat_build(username, coprname, build_id):
    build = builds_logic.BuildsLogic.get(build_id).first()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username=username, coprname=coprname).first()

    if not build: # hey, this Build doesn't exist
        return page_not_found('Build with id {0} does not exist.'.format(build_id))

    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr {0}/{1} does not exist.'.format(username, coprname))

    # TODO: do intersection of chroots with currently active?
    new_build = models.Build()
    for a in ['pkgs', 'repos', 'memory_reqs', 'timeout']:
        setattr(new_build, a, getattr(build, a))
    builds_logic.BuildsLogic.new(flask.g.user, new_build, copr)

    db.session.commit()
    flask.flash('Build was resubmitted')

    return flask.redirect(flask.url_for('coprs_ns.copr_builds', username = username, coprname = coprname))
