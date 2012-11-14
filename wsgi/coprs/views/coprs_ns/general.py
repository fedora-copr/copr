import flask

from coprs import db, page_not_found
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.views.misc import login_required

coprs_ns = flask.Blueprint('coprs_ns',
                           __name__,
                           url_prefix = '/coprs')

@coprs_ns.route('/', defaults = {'page': 1})
@coprs_ns.route('/<int:page>/')
def coprs_show(page = 1):
    query = db.session.query(models.Copr, db.func.count(models.Build.id)).\
                       outerjoin(models.Copr.builds).\
                       group_by(models.Copr.id)
    paginator = helpers.Paginator(query, query.count(), page)

    if paginator.sliced_query:
        coprs, build_counts = zip(*paginator.sliced_query)
    else:
        coprs, build_counts = [], []
    return flask.render_template('coprs/show.html', coprs = coprs, build_counts = build_counts, paginator = paginator)


@coprs_ns.route('/owned/<name>/', defaults = {'page': 1})
@coprs_ns.route('/owned/<name>/<int:page>/')
def coprs_by_owner(name = None, page = 1):
    query = db.session.query(models.Copr, db.func.count(models.Build.id)).\
                       join(models.Copr.owner).\
                       outerjoin(models.Copr.builds).\
                       filter(models.User.openid_name == models.User.openidize_name(name)).\
                       group_by(models.Copr.id)
    paginator = helpers.Paginator(query, query.count(), page)

    if paginator.sliced_query:
        coprs, build_counts = zip(*paginator.sliced_query)
    else:
        coprs, build_counts = [], []
    return flask.render_template('coprs/show.html', coprs = coprs, build_counts = build_counts, paginator = paginator)


@coprs_ns.route('/allowed/<name>/', defaults = {'page': 1})
@coprs_ns.route('/allowed/<name>/<int:page>/')
def coprs_by_allowed(name = None, page = 1):
    query = db.session.query(models.Copr, models.CoprPermission, models.User, db.func.count(models.Build.id)).\
                       outerjoin(models.Copr.builds).\
                       join(models.Copr.copr_permissions).\
                       join(models.CoprPermission.user).\
                       filter(models.User.openid_name == models.User.openidize_name(name)).\
                       filter(models.CoprPermission.approved == True).\
                       group_by(models.Copr.id)
    paginator = helpers.Paginator(query, query.count(), page)

    if paginator.sliced_query:
        coprs, build_counts = zip(*map(lambda x: (x[0], x[3]), paginator.sliced_query))
    else:
        coprs, build_counts = [], []
    return flask.render_template('coprs/show.html', coprs = coprs, build_counts = build_counts, paginator = paginator)


@coprs_ns.route('/add/')
def copr_add():
    form = forms.CoprForm()
    if flask.g.user is None:
        return flask.redirect(flask.url_for('misc.login'))

    return flask.render_template('coprs/add.html', form = form)


@coprs_ns.route('/new/', methods=['POST'])
@login_required
def copr_new():
    form = forms.CoprForm()
    if form.validate_on_submit():
        copr = models.Copr(name = form.name.data,
                           chroots = ' '.join(form.chroots),
                           repos = form.repos.data.replace('\n', ' '),
                           owner = flask.g.user)

        db.session.add(copr)
        db.session.commit()

        flask.flash('New entry was successfully posted')
        return flask.redirect(flask.url_for('coprs_ns.coprs_show'))
    else:
        return flask.render_template('coprs/add.html', form = form)


@coprs_ns.route('/detail/<name>/')
def copr_detail(name = None):
    form = forms.BuildForm()
    try: # query will raise an index error, if Copr doesn't exist
        copr = models.Copr.query.outerjoin(models.Copr.builds).\
                                 join(models.Copr.owner).\
                                 options(db.contains_eager(models.Copr.builds), db.contains_eager(models.Copr.owner)).\
                                 filter(models.Copr.name == name).\
                                 order_by(models.Build.submitted_on.desc())[0:10][0] # we retrieved all builds, but we got one copr in a list...
    except IndexError:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    permissions = models.CoprPermission.query.join(models.CoprPermission.user).\
                                              options(db.contains_eager(models.CoprPermission.user)).\
                                              filter(models.CoprPermission.copr_id == copr.id).\
                                              all()

    return flask.render_template('coprs/detail.html', copr = copr, form = form, permissions = permissions)


@coprs_ns.route('/edit/<name>/')
@login_required
def copr_edit(name = None):
    query = db.session.query(models.Copr, models.CoprPermission).\
                       outerjoin(models.CoprPermission).\
                       filter(models.Copr.name == name).\
                       all()
    copr = query[0][0]
    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    form = forms.CoprForm(obj = copr)

    permissions = map(lambda x: x[1], query)
    permissions = filter(lambda x: x, permissions) # throw away None away
    permissions_form = forms.DynamicPermissionsFormFactory.create_form_cls(permissions)()

    return flask.render_template('coprs/edit.html',
                                 copr = copr,
                                 form = form,
                                 permissions = permissions,
                                 permissions_form = permissions_form)


@coprs_ns.route('/update/<name>/', methods = ['POST'])
@login_required
def copr_update(name = None):
    form = forms.CoprForm()
    copr = models.Copr.query.filter(models.Copr.name == name).first()
    # only owner can update a copr
    if flask.g.user != copr.owner:
        flask.flash('Only owners may update their Coprs.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = form.name.data))

    if form.validate_on_submit():
        # we don't change owner (yet)
        updated = models.Copr.query.filter(models.Copr.name == name).\
                                    update({'name': form.name.data,
                                            'chroots': ' '.join(form.chroots),
                                            'repos': form.repos.data.replace('\n', ' ')})
        db.session.commit()
        flask.flash('Copr was updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = form.name.data))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)


@coprs_ns.route('/apply_for_building/<name>/', methods = ['POST'])
@login_required
def copr_apply_for_building(name = None):
    query = db.session.query(models.Copr, models.CoprPermission).\
                       outerjoin(models.CoprPermission).\
                       filter(models.Copr.name == name).\
                       filter(db.or_(models.CoprPermission.user == flask.g.user, models.CoprPermission.user == None)).\
                       first()
    copr = query[0]
    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    if copr.owner == flask.g.user:
        flask.flash('Owner cannot request permissions for his own copr.')
    elif query[1]:
        flask.flash('You are already listed in permissions for Copr "{0}".'.format(copr.name))
    else:
        perm = models.CoprPermission(user = flask.g.user, copr = copr, approved = False)
        db.session.add(perm)
        db.session.commit()
        flask.flash('You have successfuly applied for building in Copr "{0}".'.format(copr.name))

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = copr.name))


@coprs_ns.route('/give_up_building/<name>/', methods = ['POST'])
@login_required
def copr_give_up_building(name = None):
    query = db.session.query(models.Copr, models.CoprPermission).\
                       outerjoin(models.CoprPermission).\
                       filter(models.Copr.name == name).\
                       filter(models.CoprPermission.user == flask.g.user).\
                       first()
    copr = query[0]
    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))

    if not query[1]:
        flask.flash('You are already not in permissions for Copr "{0}".'.format(copr.name))
    else:
        db.session.delete(query[1]) # TODO: do we really want to delete this, or just inactivate?
        db.session.commit()
        flask.flash('You have successfuly given up building in Copr "{0}".'.format(copr.name))

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = copr.name))


@coprs_ns.route('/update_permissions/<name>/', methods = ['POST'])
@login_required
def copr_update_permissions(name = None): #TODO: optimize!
    copr = models.Copr.query.filter(models.Copr.name == name).first()
    permissions = models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).all()
    permissions_form = forms.DynamicPermissionsFormFactory.create_form_cls(permissions)()

    # only owner can update copr permissions
    if flask.g.user != copr.owner:
        flask.flash('Only owners may update their Coprs permissions.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = copr.name))

    if permissions_form.validate_on_submit():
        # we don't change owner (yet)
        for perm in permissions:
            models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).\
                                        filter(models.CoprPermission.user_id == perm.user_id).\
                                        update({'approved': permissions_form['user_{0}'.format(perm.user_id)].data})
        db.session.commit()
        flask.flash('Copr permissions were updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', name = copr.name))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)
