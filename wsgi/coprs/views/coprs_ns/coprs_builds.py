import time

import flask

from coprs import db, page_not_found
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.logic import builds_logic
from coprs.logic import coprs_logic

from coprs.views.misc import login_required
from coprs.views.coprs_ns import coprs_ns

@coprs_ns.route('/detail/<username>/<coprname>/builds/', defaults = {'page': 1})
@coprs_ns.route('/detail/<username>/<coprname>/builds/<int:page>/')
def copr_show_builds(username, coprname, page = 1):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    builds_query = builds_logic.BuildsLogic.get_multiple(flask.g.user, copr = copr)

    paginator = helpers.Paginator(builds_query, copr.build_count, page, per_page_override = 20)
    return flask.render_template('coprs/show_builds.html', builds = paginator.sliced_query, paginator = paginator)


@coprs_ns.route('/detail/<username>/<coprname>/add_build/', methods = ["POST"])
@login_required
def copr_add_build(username, coprname):
    form = forms.BuildForm()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    if form.validate_on_submit() and flask.g.user.can_build_in(copr):
        build = models.Build(pkgs = form.pkgs.data.replace('\n', ' '),
                             copr = copr,
                             chroots = copr.chroots,
                             repos = copr.repos,
                             user = flask.g.user,
                             submitted_on = int(time.time()))
        if flask.g.user.proven:
            build.memory_reqs = form.memory_reqs.data
            build.timeout = form.timeout.data

        builds_logic.BuildsLogic.new(flask.g.user, build, copr, check_authorized = False) # we're checking authorization above for now
        db.session.commit()

        flask.flash("Build was added")
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = username, coprname = copr.name))
    else:
        return flask.render_template('coprs/detail.html', copr = copr, form = form)


@coprs_ns.route('/detail/<username>/<coprname>/cancel_build/<int:build_id>/')
@login_required
def copr_cancel_build(username, coprname, build_id):
    # only the user who ran the build can cancel it
    build = builds_logic.BuildsLogic.get(flask.g.user, build_id).first()
    if not build: # hey, this Build doesn't exist
        return page_not_found('Build with id {0} does not exist.'.format(build_id))
    try:
        builds_logic.BuildsLogic.cancel_build(flask.g.user, build)
    except exceptions.InsufficientRightsException as ex:
        flask.flask(ex.message)
    else:
        db.session.commit()
        flask.flash('Build was canceled')

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = username, coprname = coprname))
