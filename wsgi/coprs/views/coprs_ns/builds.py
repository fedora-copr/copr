import time

import flask

from coprs import db, page_not_found
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.views.misc import login_required

from coprs.views.coprs_ns.general import coprs_ns

@coprs_ns.route('/detail/<name>/builds/', defaults = {'page': 1})
@coprs_ns.route('/detail/<name>/builds/<int:page>/')
def copr_show_builds(name, page = 1):
    query = models.Build.query.join(models.Copr.builds).\
                               options(db.contains_eager(models.Build.copr)).\
                               filter(models.Copr.name == name).\
                               order_by(models.Build.submitted_on.desc())

    build_count = query.count()
    if build_count == 0: # no builds => we still need Copr
        copr = models.Copr.query.filter(models.Copr.name == name).first()
        if not copr: # hey, this Copr doesn't exist
            return page_not_found('Copr with name {0} does not exist.'.format(name))

    paginator = helpers.Paginator(query, build_count, page, per_page_override = 20)
    return flask.render_template('coprs/show_builds.html', builds = paginator.sliced_query, paginator = paginator)


@coprs_ns.route('/detail/<name>/add_build/', methods = ["POST"])
@login_required
def copr_add_build(name = None):
    form = forms.BuildForm()
    copr = models.Copr.query.filter(models.Copr.name == name).first()
    if not copr: # hey, this Copr doesn't exist
        return page_not_found('Copr with name {0} does not exist.'.format(name))

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

        db.session.add(build)
        db.session.commit()

        flask.flash("Build was added")
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = copr.name))
    else:
        return flask.render_template('coprs/detail.html', copr = copr, form = form)


@coprs_ns.route('/detail/<name>/cancel_build/<int:build_id>/')
@login_required
def copr_cancel_build(name, build_id):
    # only the user who ran the build can cancel it
    build = models.Build.query.filter(models.Build.id == build_id).first()
    if not build: # hey, this Copr doesn't exist
        return page_not_found('Build with id {0} does not exist.'.format(build_id))
    if build.user_id != flask.g.user.id:
        flask.flash('You can only cancel your own builds.')
    else:
        build.canceled = True
        db.session.commit()
        flask.flash('Build was canceled')

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = name))
