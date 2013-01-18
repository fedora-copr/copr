import time

import flask

from coprs import db, page_not_found
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.views.misc import login_required

from coprs.views.coprs_ns import coprs_ns

from coprs.logic import builds_logic
from coprs.logic import coprs_logic

@coprs_ns.route('/', defaults = {'page': 1})
@coprs_ns.route('/<int:page>/')
def coprs_show(page = 1):
    if flask.g.user:
        query = coprs_logic.CoprsLogic.get_multiple(flask.g.user, user_relation='owned', username=flask.g.user.name)
    else:
        query = coprs_logic.CoprsLogic.get_multiple(flask.g.user)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template('coprs/show.html', coprs=coprs, paginator=paginator)


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
@login_required
def copr_add():
    form = forms.CoprFormFactory.create_form_cls()()

    return flask.render_template('coprs/add.html', form = form)


@coprs_ns.route('/new/', methods=['POST'])
@login_required
def copr_new():
    form = forms.CoprFormFactory.create_form_cls()()
    if form.validate_on_submit():
        copr = models.Copr(name = form.name.data,
                           repos = form.repos.data.replace('\n', ' '),
                           owner = flask.g.user,
                           created_on = int(time.time()))
        coprs_logic.CoprsLogic.new(flask.g.user, copr, check_for_duplicates = False) # form validation checks for duplicates
        coprs_logic.CoprChrootLogic.new_from_names(flask.g.user, copr, form.selected_chroots)
        db.session.commit()
        flask.flash('New copr was successfully created.')

        if form.initial_pkgs.data:
            build = models.Build(pkgs = form.initial_pkgs.data.replace('\n', ' '),
                                 copr = copr,
                                 repos = copr.repos,
                                 chroots = ' '.join(map(lambda x: x.chroot_name, copr.mock_chroots)),
                                 user = flask.g.user,
                                 submitted_on = int(time.time()))
            # no need to check for authorization here
            builds_logic.BuildsLogic.new(flask.g.user, build, copr, check_authorized = False)
            db.session.commit()
            flask.flash('Initial packages were successfully submitted for building.')

        return flask.redirect(flask.url_for('coprs_ns.coprs_show'))
    else:
        return flask.render_template('coprs/add.html', form = form)

@coprs_ns.route('/detail/<username>/<coprname>/')
def copr_detail(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    return flask.render_template('coprs/detail/overview.html',
                                 copr=copr)

@coprs_ns.route('/detail/<username>/<coprname>/permissions/')
def copr_permissions(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    permissions = coprs_logic.CoprsPermissionLogic.get_for_copr(flask.g.user, copr).all()
    if flask.g.user:
        user_perm = flask.g.user.permissions_for_copr(copr)
    else:
        user_perm = None

    permissions_applier_form = None
    permissions_form = None

    # generate a proper form for displaying
    if flask.g.user:
        if flask.g.user.can_edit(copr):
            permissions_form = forms.PermissionsFormFactory.create_form_cls(permissions)()
        else:
            # https://github.com/ajford/flask-wtf/issues/58
            permissions_applier_form = forms.PermissionsApplierFormFactory.create_form_cls(user_perm)(formdata=None)

    return flask.render_template('coprs/detail/permissions.html',
                                 copr = copr,
                                 permissions_form = permissions_form,
                                 permissions_applier_form = permissions_applier_form,
                                 permissions = permissions,
                                 current_user_permissions = user_perm)

@coprs_ns.route('/detail/<username>/<coprname>/builds/')
def copr_builds(username, coprname, build_form = None):
    try: # query[0:10][0] will raise an index error, if Copr doesn't exist
        query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname, with_builds = True)
        copr = query[0:10][0]# we retrieved all builds, but we got one copr in a list...
    except IndexError:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    return flask.render_template('coprs/detail/builds.html',
                                 copr = copr)

@coprs_ns.route('/detail/<username>/<coprname>/edit/')
@login_required
def copr_edit(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))
    form = forms.CoprFormFactory.create_form_cls(copr.mock_chroots)(obj=copr)

    return flask.render_template('coprs/edit.html',
                                 copr=copr,
                                 form=form)


@coprs_ns.route('/detail/<username>/<coprname>/update/', methods = ['POST'])
@login_required
def copr_update(username, coprname):
    form = forms.CoprFormFactory.create_form_cls()()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    # only owner can update a copr
    if not flask.g.user.can_edit(copr):
        flask.flash('Only owners and admins may update their Coprs.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = form.name.data))

    if form.validate_on_submit():
        # we don't change owner (yet)
        copr.name = form.name.data
        copr.repos = form.repos.data.replace('\n', ' ')
        coprs_logic.CoprChrootLogic.update_from_names(flask.g.user, copr, form.selected_chroots)

        coprs_logic.CoprsLogic.update(flask.g.user, copr, check_for_duplicates = False) # form validation checks for duplicates
        db.session.commit()
        flask.flash('Copr was updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = username, coprname = form.name.data))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)


@coprs_ns.route('/detail/<username>/<coprname>/permissions_applier_change/', methods = ['POST'])
@login_required
def copr_permissions_applier_change(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    permission = coprs_logic.CoprsPermissionLogic.get(flask.g.user, copr, flask.g.user).first()
    applier_permissions_form = forms.PermissionsApplierFormFactory.create_form_cls(permission)()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    if copr.owner == flask.g.user:
        flask.flash('Owner cannot request permissions for his own copr.')
    elif applier_permissions_form.validate_on_submit():
        # we rely on these to be 0 or 1 from form. TODO: abstract from that
        new_builder = applier_permissions_form.copr_builder.data
        new_admin = applier_permissions_form.copr_admin.data
        coprs_logic.CoprsPermissionLogic.update_permissions_by_applier(flask.g.user, copr, permission, new_builder, new_admin)
        db.session.commit()
        flask.flash('Successfuly updated permissions do Copr "{0}".'.format(copr.name))

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))

@coprs_ns.route('/detail/<username>/<coprname>/update_permissions/', methods = ['POST'])
@login_required
def copr_update_permissions(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    permissions = copr.copr_permissions
    permissions_form = forms.PermissionsFormFactory.create_form_cls(permissions)()

    # only owner can update copr permissions
    if not flask.g.user.can_edit(copr):
        flask.flash('Only owners and admins may update their Coprs permissions.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))

    if permissions_form.validate_on_submit():
        # we don't change owner (yet)
        for perm in permissions:
            new_builder = permissions_form['copr_builder_{0}'.format(perm.user_id)].data
            new_admin = permissions_form['copr_admin_{0}'.format(perm.user_id)].data
            coprs_logic.CoprsPermissionLogic.update_permissions(flask.g.user, copr, perm, new_builder, new_admin)

        db.session.commit()
        flask.flash('Copr permissions were updated successfully.')

    return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))
