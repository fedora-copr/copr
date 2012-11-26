import flask

from coprs import db, page_not_found
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.views.misc import login_required

from coprs.views.coprs_ns import coprs_ns

from coprs.logic import coprs_logic

@coprs_ns.route('/', defaults = {'page': 1})
@coprs_ns.route('/<int:page>/')
def coprs_show(page = 1):
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template('coprs/show.html', coprs = coprs, paginator = paginator)


@coprs_ns.route('/owned/<username>/', defaults = {'page': 1})
@coprs_ns.route('/owned/<username>/<int:page>/')
def coprs_by_owner(username = None, page = 1):
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user, user_relation = 'owned', username = username)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template('coprs/show.html', coprs = coprs, paginator = paginator)


@coprs_ns.route('/allowed/<username>/', defaults = {'page': 1})
@coprs_ns.route('/allowed/<username>/<int:page>/')
def coprs_by_allowed(username = None, page = 1):
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user, user_relation = 'allowed', username = username)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template('coprs/show.html', coprs = coprs, paginator = paginator)


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
        coprs_logic.CoprsLogic.new(flask.g.user, copr, check_for_duplicates = False) # form validation checks for duplicates
        db.session.commit()

        flask.flash('New entry was successfully posted')
        return flask.redirect(flask.url_for('coprs_ns.coprs_show'))
    else:
        return flask.render_template('coprs/add.html', form = form)


@coprs_ns.route('/detail/<username>/<coprname>/')
def copr_detail(username, coprname):
    form = forms.BuildForm()
    try: # query[0:10][0] will raise an index error, if Copr doesn't exist
        query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname, with_builds = True)
        copr = query[0:10][0]# we retrieved all builds, but we got one copr in a list...
    except IndexError:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    permissions = coprs_logic.CoprsPermissionLogic.get_for_copr(flask.g.user, copr).all()
    return flask.render_template('coprs/detail.html', copr = copr, form = form, permissions = permissions)


@coprs_ns.route('/detail/<username>/<coprname>/edit/')
@login_required
def copr_edit(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))
    form = forms.CoprForm(obj = copr)

    permissions = coprs_logic.CoprsPermissionLogic.get_for_copr(flask.g.user, copr).all()
    permissions_form = forms.DynamicPermissionsFormFactory.create_form_cls(permissions)()

    return flask.render_template('coprs/edit.html',
                                 copr = copr,
                                 form = form,
                                 permissions = permissions,
                                 permissions_form = permissions_form)


@coprs_ns.route('/detail/<username>/<coprname>/update/', methods = ['POST'])
@login_required
def copr_update(username, coprname):
    form = forms.CoprForm()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    # only owner can update a copr
    if flask.g.user != copr.owner:
        flask.flash('Only owners may update their Coprs.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = form.name.data))

    if form.validate_on_submit():
        # we don't change owner (yet)
        copr.name = form.name.data
        copr.chroots = ' '.join(form.chroots)
        copr.repos = form.repos.data.replace('\n', ' ')

        coprs_logic.CoprsLogic.update(flask.g.user, copr, check_for_duplicates = False) # form validation checks for duplicates
        db.session.commit()
        flask.flash('Copr was updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = username, coprname = form.name.data))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)


@coprs_ns.route('/detail/<username>/<coprname>/apply_for_building/', methods = ['POST'])
@login_required
def copr_apply_for_building(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    permission = coprs_logic.CoprsPermissionLogic.get(flask.g.user, copr, flask.g.user).first()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    if copr.owner == flask.g.user:
        flask.flash('Owner cannot request permissions for his own copr.')
    elif permission:
        flask.flash('You are already listed in permissions for Copr "{0}".'.format(copr.name))
    else:
        perm = models.CoprPermission(user = flask.g.user, copr = copr, copr_builder = False)
        coprs_logic.CoprsPermissionLogic.new(flask.g.user, perm)
        db.session.commit()
        flask.flash('You have successfuly applied for building in Copr "{0}".'.format(copr.name))

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))


@coprs_ns.route('/detail/<username>/<coprname>/give_up_building/', methods = ['POST'])
@login_required
def copr_give_up_building(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    permission = coprs_logic.CoprsPermissionLogic.get(flask.g.user, copr, flask.g.user).first()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))

    if not permission:
        flask.flash('You are already not in permissions for Copr "{0}".'.format(copr.name))
    else:
        coprs_logic.CoprsPermissionLogic.delete(flask.g.user, permission) # TODO: do we really want to delete this, or just inactivate?
        db.session.commit()
        flask.flash('You have successfuly given up building in Copr "{0}".'.format(copr.name))

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))


@coprs_ns.route('/detail/<username>/<coprname>/update_permissions/', methods = ['POST'])
@login_required
def copr_update_permissions(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    permissions = copr.copr_permissions
    permissions_form = forms.DynamicPermissionsFormFactory.create_form_cls(permissions)()

    # only owner can update copr permissions
    if flask.g.user != copr.owner:
        flask.flash('Only owners may update their Coprs permissions.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))

    if permissions_form.validate_on_submit():
        # we don't change owner (yet)
        for perm in permissions:
            models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).\
                                        filter(models.CoprPermission.user_id == perm.user_id).\
                                        update({'copr_builder': permissions_form['user_{0}'.format(perm.user_id)].data})
        db.session.commit()
        flask.flash('Copr permissions were updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)
