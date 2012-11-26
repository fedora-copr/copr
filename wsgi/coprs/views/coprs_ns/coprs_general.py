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
    build_form = forms.BuildForm()
    try: # query[0:10][0] will raise an index error, if Copr doesn't exist
        query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname, with_builds = True)
        copr = query[0:10][0]# we retrieved all builds, but we got one copr in a list...
    except IndexError:
        return page_not_found('Copr with name {0} does not exist.'.format(coprname))

    permissions = coprs_logic.CoprsPermissionLogic.get_for_copr(flask.g.user, copr).all()
    if flask.g.user:
        user_perm = flask.g.user.permissions_for_copr(copr)
    else:
        user_perm = None

    permission_applier_form = forms.PermissionsApplierFormFactory.create_form_cls(user_perm)()
    return flask.render_template('coprs/detail.html',
                                 copr = copr,
                                 build_form = build_form,
                                 permission_applier_form = permission_applier_form,
                                 permissions = permissions)


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


@coprs_ns.route('/detail/<username>/<coprname>/permissions_applier_change/', methods = ['POST'])
@login_required
def copr_permissions_applier_change(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    permission = coprs_logic.CoprsPermissionLogic.get(flask.g.user, copr, flask.g.user).first()
    applier_permissions_form = forms.PermissionsApplierFormFactory.create_form_cls()()

    if not copr:
        return page_not_found('Copr with name {0} does not exist.'.format(name))
    if copr.owner == flask.g.user:
        flask.flash('Owner cannot request permissions for his own copr.')
    else: # TODO: pull this into logic
        new_builder = int(applier_permissions_form.copr_builder.data)
        new_admin = int(applier_permissions_form.copr_admin.data)
        approved_num = helpers.PermissionEnum.num('Approved')
        if permission:
            prev_builder = permission.copr_builder
            prev_admin = permission.copr_admin
            # if we had Approved before, we can have it now, otherwise not
            if new_builder == approved_num and prev_builder != new_builder or \
               new_admin == approved_num and prev_admin != new_admin:
                flask.flash('User can\'t approve himself.')
            else:
                permission.copr_builder = new_builder
                permission.copr_admin = new_admin
                db.session.commit()
                flask.flash('Successfuly updated your permissions in Copr "{0}".'.format(copr.name))
        else:
            if new_builder == approved_num or new_admin == approved_num:
                flask.flash('User can\'t approve himself.')
            else:
                perm = models.CoprPermission(user = flask.g.user, copr = copr, copr_builder = new_builder, copr_admin = new_admin)
                coprs_logic.CoprsPermissionLogic.new(flask.g.user, perm)
                db.session.commit()
                flask.flash('Successfuly applied for permissions in Copr "{0}".'.format(copr.name))

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
            copr_builder = helpers.PermissionEnum.num('Asked')
            copr_admin = helpers.PermissionEnum.num('Asked')
            if permissions_form['copr_builder_{0}'.format(perm.user_id)].data:
                copr_builder = helpers.PermissionEnum.num('Approved')
            if permissions_form['copr_admin_{0}'.format(perm.user_id)].data:
                copr_admin = helpers.PermissionEnum.num('Approved')


            models.CoprPermission.query.filter(models.CoprPermission.copr_id == copr.id).\
                                        filter(models.CoprPermission.user_id == perm.user_id).\
                                        update({'copr_builder': copr_builder,
                                                'copr_admin': copr_admin})
        db.session.commit()
        flask.flash('Copr permissions were updated successfully.')
        return flask.redirect(flask.url_for('coprs_ns.copr_detail', username = copr.owner.name, coprname = copr.name))
    else:
        return flask.render_template('coprs/edit.html', copr = copr, form = form)
