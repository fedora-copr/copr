import os
import time

import flask
import platform
import smtplib
import sqlalchemy
from email.mime.text import MIMEText

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models

from coprs.views.misc import login_required, page_not_found

from coprs.views.coprs_ns import coprs_ns

from coprs.logic import builds_logic
from coprs.logic import coprs_logic
from coprs.helpers import parse_package_name, render_repo


@coprs_ns.route("/", defaults={"page": 1})
@coprs_ns.route("/<int:page>/")
def coprs_show(page=1):
    query = coprs_logic.CoprsLogic.get_multiple(
        flask.g.user, with_mock_chroots=False)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template("coprs/show.html",
                                 coprs=coprs,
                                 paginator=paginator)


@coprs_ns.route("/<username>/", defaults={"page": 1})
@coprs_ns.route("/<username>/<int:page>/")
def coprs_by_owner(username=None, page=1):
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user,
                                                user_relation="owned",
                                                username=username,
                                                with_mock_chroots=False)

    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template("coprs/show.html",
                                 coprs=coprs,
                                 paginator=paginator)


@coprs_ns.route("/<username>/allowed/", defaults={"page": 1})
@coprs_ns.route("/<username>/allowed/<int:page>/")
def coprs_by_allowed(username=None, page=1):
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user,
                                                user_relation="allowed",
                                                username=username,
                                                with_mock_chroots=False)
    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template("coprs/show.html",
                                 coprs=coprs,
                                 paginator=paginator)


@coprs_ns.route("/fulltext/", defaults={"page": 1})
@coprs_ns.route("/fulltext/<int:page>/")
def coprs_fulltext_search(page=1):
    fulltext = flask.request.args.get("fulltext", "")
    try:
        query = coprs_logic.CoprsLogic.get_multiple_fulltext(
            flask.g.user, fulltext)
    except ValueError as e:
        flask.flash(str(e))
        return flask.redirect(flask.request.referrer or
                              flask.url_for("coprs_ns.coprs_show"))

    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query
    return flask.render_template("coprs/show.html",
                                 coprs=coprs,
                                 paginator=paginator,
                                 fulltext=fulltext)


@coprs_ns.route("/<username>/add/")
@login_required
def copr_add(username):
    form = forms.CoprFormFactory.create_form_cls()()

    return flask.render_template("coprs/add.html", form=form)


@coprs_ns.route("/<username>/new/", methods=["POST"])
@login_required
def copr_new(username):
    """
    Receive information from the user on how to create its new copr
    and create it accordingly.
    """

    form = forms.CoprFormFactory.create_form_cls()()
    if form.validate_on_submit():
        copr = coprs_logic.CoprsLogic.add(
            flask.g.user,
            name=form.name.data,
            repos=form.repos.data.replace("\n", " "),
            selected_chroots=form.selected_chroots,
            description=form.description.data,
            instructions=form.instructions.data)

        db.session.commit()
        flask.flash("New project was successfully created.")

        if form.initial_pkgs.data:
            # we need to build each package separately now
            pkgs = form.initial_pkgs.data.replace("\n", " ").split(" ")
            for pkg in pkgs:
                builds_logic.BuildsLogic.add(
                    flask.g.user,
                    pkgs=pkg,
                    copr=copr)

            db.session.commit()
            flask.flash("Initial packages were successfully submitted "
                        "for building.")

        return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                            username=flask.g.user.name,
                                            coprname=copr.name))
    else:
        return flask.render_template("coprs/add.html", form=form)


@coprs_ns.route("/<username>/<coprname>/")
def copr_detail(username, coprname):
    query = coprs_logic.CoprsLogic.get(
        flask.g.user, username, coprname, with_mock_chroots=True)
    form = forms.CoprLegalFlagForm()
    try:
        copr = query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    return flask.render_template("coprs/detail/overview.html",
                                 copr=copr,
                                 form=form)


@coprs_ns.route("/<username>/<coprname>/permissions/")
def copr_permissions(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    if not copr:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    permissions = coprs_logic.CoprPermissionsLogic.get_for_copr(
        flask.g.user, copr).all()
    if flask.g.user:
        user_perm = flask.g.user.permissions_for_copr(copr)
    else:
        user_perm = None

    permissions_applier_form = None
    permissions_form = None

    # generate a proper form for displaying
    if flask.g.user:
        if flask.g.user.can_edit(copr):
            permissions_form = forms.PermissionsFormFactory.create_form_cls(
                permissions)()
        else:
            # https://github.com/ajford/flask-wtf/issues/58
            permissions_applier_form = \
                forms.PermissionsApplierFormFactory.create_form_cls(
                    user_perm)(formdata=None)

    return flask.render_template(
        "coprs/detail/permissions.html",
        copr=copr,
        permissions_form=permissions_form,
        permissions_applier_form=permissions_applier_form,
        permissions=permissions,
        current_user_permissions=user_perm)


@coprs_ns.route("/<username>/<coprname>/edit/")
@login_required
def copr_edit(username, coprname, form=None):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()

    if not copr:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    if not form:
        form = forms.CoprFormFactory.create_form_cls(
            copr.mock_chroots)(obj=copr)

    return flask.render_template("coprs/detail/edit.html",
                                 copr=copr,
                                 form=form)


@coprs_ns.route("/<username>/<coprname>/update/", methods=["POST"])
@login_required
def copr_update(username, coprname):
    form = forms.CoprFormFactory.create_form_cls()()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if form.validate_on_submit():
        # we don"t change owner (yet)
        copr.name = form.name.data
        copr.repos = form.repos.data.replace("\n", " ")
        copr.description = form.description.data
        copr.instructions = form.instructions.data
        coprs_logic.CoprChrootsLogic.update_from_names(
            flask.g.user, copr, form.selected_chroots)

        try:
            # form validation checks for duplicates
            coprs_logic.CoprsLogic.update(
                flask.g.user, copr, check_for_duplicates=False)
        except (exceptions.ActionInProgressException,
                exceptions.InsufficientRightsException) as e:

            flask.flash(str(e))
            db.session.rollback()
        else:
            flask.flash("Project was updated successfully.")
            db.session.commit()

        return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                            username=username,
                                            coprname=copr.name))
    else:
        return copr_edit(username, coprname, form)


@coprs_ns.route("/<username>/<coprname>/permissions_applier_change/",
                methods=["POST"])
@login_required
def copr_permissions_applier_change(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    permission = coprs_logic.CoprPermissionsLogic.get(
        flask.g.user, copr, flask.g.user).first()
    applier_permissions_form = \
        forms.PermissionsApplierFormFactory.create_form_cls(permission)()

    if not copr:
        return page_not_found(
            "Project with name {0} does not exist.".format(coprname))

    if copr.owner == flask.g.user:
        flask.flash("Owner cannot request permissions for his own project.")
    elif applier_permissions_form.validate_on_submit():
        # we rely on these to be 0 or 1 from form. TODO: abstract from that
        if permission is not None:
            old_builder = permission.copr_builder
            old_admin = permission.copr_admin
        else:
            old_builder = 0
            old_admin = 0
        new_builder = applier_permissions_form.copr_builder.data
        new_admin = applier_permissions_form.copr_admin.data
        coprs_logic.CoprPermissionsLogic.update_permissions_by_applier(
            flask.g.user, copr, permission, new_builder, new_admin)
        db.session.commit()
        flask.flash(
            "Successfuly updated permissions for project '{0}'."
            .format(copr.name))
        admin_mails = [copr.owner.mail]
        for perm in copr.copr_permissions:
            # this 2 means that his status (admin) is approved
            if perm.copr_admin == 2:
                admin_mails.append(perm.user.mail)

        # sending emails
        if flask.current_app.config.get("SEND_EMAILS", False):
            for mail in admin_mails:
                msg = MIMEText("{6} is asking for these permissions:\n\n"
                               "Builder: {0} -> {1}\nAdmin: {2} -> {3}\n\n"
                               "Project: {4}\nOwner: {5}".format(
                                        helpers.PermissionEnum(old_builder),
                                        helpers.PermissionEnum(new_builder),
                                        helpers.PermissionEnum(old_admin),
                                        helpers.PermissionEnum(new_admin),
                                        copr.name, copr.owner.name, flask.g.user.name), "plain")
                msg["Subject"] = "[Copr] {0}: {1} is asking permissons".format(copr.name, flask.g.user.name)
                msg["From"] = "root@{0}".format(platform.node())
                msg["To"] = mail
                s = smtplib.SMTP("localhost")
                s.sendmail("root@{0}".format(platform.node()), mail , msg.as_string())
                s.quit()


    return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                        username=copr.owner.name,
                                        coprname=copr.name))


@coprs_ns.route("/<username>/<coprname>/update_permissions/", methods=["POST"])
@login_required
def copr_update_permissions(username, coprname):
    query = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname)
    copr = query.first()
    permissions = copr.copr_permissions
    permissions_form = forms.PermissionsFormFactory.create_form_cls(
        permissions)()

    if permissions_form.validate_on_submit():
        # we don't change owner (yet)
        try:
            # if admin is changing his permissions, his must be changed last
            # so that we don't get InsufficientRightsException
            permissions.sort(
                cmp=lambda x, y: -1 if y.user_id == flask.g.user.id else 1)
            for perm in permissions:
                old_builder = perm.copr_builder
                old_admin = perm.copr_admin
                new_builder = permissions_form[
                    "copr_builder_{0}".format(perm.user_id)].data
                new_admin = permissions_form[
                    "copr_admin_{0}".format(perm.user_id)].data
                coprs_logic.CoprPermissionsLogic.update_permissions(
                    flask.g.user, copr, perm, new_builder, new_admin)
                if flask.current_app.config.get("SEND_EMAILS", False):
                    if old_builder is not new_builder or \
                       old_admin is not new_admin:
                        msg = MIMEText("Your permissions have changed:\n\n"
                                       "Builder: {0} -> {1}\nAdmin: {2} -> {3}\n\n"
                                       "Project: {4}\nOwner: {5}".format(
                                                helpers.PermissionEnum(old_builder),
                                                helpers.PermissionEnum(new_builder),
                                                helpers.PermissionEnum(old_admin),
                                                helpers.PermissionEnum(new_admin),
                                                copr.name, copr.owner.name), "plain")
                        msg["Subject"] = "[Copr] {0}: Your permissions have changed".format(copr.name)
                        msg["From"] = "root@{0}".format(platform.node())
                        msg["To"] = perm.user.mail
                        s = smtplib.SMTP("localhost")
                        s.sendmail("root@{0}".format(platform.node()),perm.user.mail , msg.as_string())
                        s.quit()

        # for now, we don't check for actions here, as permissions operation
        # don't collide with any actions
        except exceptions.InsufficientRightsException as e:
            db.session.rollback()
            flask.flash(str(e))
        else:
            db.session.commit()
            flask.flash("Project permissions were updated successfully.")

    return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                        username=copr.owner.name,
                                        coprname=copr.name))


@coprs_ns.route("/<username>/<coprname>/delete/", methods=["GET", "POST"])
@login_required
def copr_delete(username, coprname):
    form = forms.CoprDeleteForm()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if form.validate_on_submit() and copr:
        builds_query = builds_logic.BuildsLogic.get_multiple(
        flask.g.user, copr=copr)
        try:
            for build in builds_query:
                builds_logic.BuildsLogic.delete_build(flask.g.user, build)
            coprs_logic.CoprsLogic.delete(flask.g.user, copr)
        except (exceptions.ActionInProgressException,
                exceptions.InsufficientRightsException) as e:

            db.session.rollback()
            flask.flash(str(e))
            return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                                username=username,
                                                coprname=coprname))
        else:
            db.session.commit()
            flask.flash("Project was deleted successfully.")
            return flask.redirect(flask.url_for("coprs_ns.coprs_by_owner",
                                                username=username))
    else:
        if copr:
            return flask.render_template("coprs/detail/delete.html",
                                         form=form, copr=copr)
        else:
            return page_not_found("Project {0}/{1} does not exist"
                                  .format(username, coprname))


@coprs_ns.route("/<username>/<coprname>/legal_flag/", methods=["POST"])
@login_required
def copr_legal_flag(username, coprname):
    form = forms.CoprLegalFlagForm()
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    legal_flag = models.LegalFlag(raise_message=form.comment.data,
                                  raised_on=int(time.time()),
                                  copr=copr,
                                  reporter=flask.g.user)
    db.session.add(legal_flag)
    db.session.commit()

    send_to = app.config["SEND_LEGAL_TO"] or ["root@localhost"]
    hostname = platform.node()
    navigate_to = "\nNavigate to http://{0}{1}".format(
        hostname, flask.url_for("admin_ns.legal_flag"))

    contact = "\nContact on owner is: {0} <{1}>".format(username,
                                                        copr.owner.mail)

    reported_by = "\nReported by {0} <{1}>".format(flask.g.user.name,
                                                   flask.g.user.mail)

    try:
        msg = MIMEText(
            form.comment.data + navigate_to + contact + reported_by, "plain")
    except UnicodeEncodeError:
        msg = MIMEText(form.comment.data.encode(
            "utf-8") + navigate_to + contact + reported_by, "plain", "utf-8")

    msg["Subject"] = "Legal flag raised on {0}".format(coprname)
    msg["From"] = "root@{0}".format(hostname)
    msg["To"] = ", ".join(send_to)
    s = smtplib.SMTP("localhost")
    s.sendmail("root@{0}".format(hostname), send_to, msg.as_string())
    s.quit()

    flask.flash("Admin was noticed about your report"
                " and will investigate the project shortly.")

    return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                        username=username,
                                        coprname=coprname))


@coprs_ns.route("/<username>/<coprname>/repo/<chroot>/", defaults={"repofile": None})
@coprs_ns.route("/<username>/<coprname>/repo/<chroot>/<repofile>")
def generate_repo_file(username, coprname, chroot, repofile):
    """ Generate repo file for a given repo name.
        Reponame = username-coprname """
    # This solution is used because flask splits off the last part after a
    # dash, therefore user-re-po resolves to user-re/po instead of user/re-po
    # FAS usernames may not contain dashes, so this construction is safe.

    reponame = "{0}-{1}".format(username, coprname)

    if repofile is not None and repofile != username + '-' + coprname + '-' + chroot + '.repo':
        return page_not_found(
            "Repository filename does not match expected: {0}"
            .format(repofile))


    if "-" not in reponame:
        return page_not_found(
            "Bad repository name: {0}. Must be username-projectname"
            .format(reponame))

    copr = None
    try:
        # query.one() is used since it fetches all builds, unlike
        # query.first().
        copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname,
                                          with_builds=True).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return page_not_found(
            "Project {0}/{1} does not exist".format(username, coprname))

    try:
        mock_chroot = coprs_logic.MockChrootsLogic.get_from_name(chroot).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return page_not_found("Chroot {0} does not exist".format(chroot))
    except ValueError as e:
        return page_not_found(str(e))

    url = ""
    for build in copr.builds:
        if build.results:
            url = build.results
            break

    if not url:
        return page_not_found(
            "Repository not initialized: No finished builds in {0}/{1}."
            .format(username, coprname))

    response = flask.make_response(render_repo(copr, mock_chroot, url))
    response.mimetype = "text/plain"
    response.headers["Content-Disposition"] = "filename={0}.repo".format(
        reponame)

    return response


@coprs_ns.route("/<username>/<coprname>/monitor/")
def copr_build_monitor(username, coprname):
    query = coprs_logic.CoprsLogic.get(
        flask.g.user, username, coprname, with_mock_chroots=True)
    form = forms.CoprLegalFlagForm()
    try:
        copr = query.one()
    except sqlalchemy.orm.exc.NoResultFound:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    builds_query = builds_logic.BuildsLogic.get_multiple(
        flask.g.user, copr=copr)
    builds = builds_query.order_by("-id").all()

    # please don"t waste time trying to decipher this
    # the only reason why this is necessary is non-existent
    # database design
    #
    # loop goes through builds trying to approximate
    # per-package results based on previous builds
    # - it can"t determine build results if build contains
    # more than one package as this data is not available

    out = {}
    build = None
    chroots = set([chroot.name for chroot in copr.active_chroots])
    latest_build = None

    if builds:
        latest_build = builds[0]
        chroots.union([chroot.name for chroot in latest_build.build_chroots])

    chroots = sorted(chroots)

    for build in builds:
        chroot_results = {chroot.name: chroot.state
                          for chroot in build.build_chroots}

        build_results = []
        for chroot_name in chroots:
            if chroot_name in chroot_results:
                build_results.append((build.id, chroot_results[chroot_name]))
            else:
                build_results.append((build.id, None))

        for pkg_url in build.pkgs.split():
            pkg = os.path.basename(pkg_url)
            pkg_name = parse_package_name(pkg)

            if pkg_name in out:
                continue

            out[pkg_name] = build_results

    return flask.render_template("coprs/detail/monitor.html",
                                 copr=copr,
                                 build=latest_build,
                                 chroots=chroots,
                                 packages=sorted(out.iteritems()),
                                 form=form)
