from io import BytesIO
from zlib import compress, decompress

import flask
from flask import Response

from coprs import db
from coprs import forms

from coprs.logic import coprs_logic
from coprs.logic.coprs_logic import CoprChrootsLogic

from coprs.views.misc import login_required, page_not_found
from coprs.views.coprs_ns import coprs_ns


@coprs_ns.route("/<username>/<coprname>/edit_chroot/<chrootname>/")
@login_required
def chroot_edit(username, coprname, chrootname):
    copr = coprs_logic.CoprsLogic.get(username, coprname).first()
    if not copr:
        return page_not_found(
            "Project with name {0} does not exist.".format(coprname))

    try:
        chroot = CoprChrootsLogic.get_by_name_safe(copr, chrootname)
    except (ValueError, KeyError, RuntimeError) as e:
        return page_not_found(str(e))

    if not chroot:
        return page_not_found(
            "Chroot name {0} does not exist.".format(chrootname))

    # todo: get COPR_chroot, not mock chroot, WTF?!
    # form = forms.ChrootForm(buildroot_pkgs=copr.buildroot_pkgs(chroot))
    form = forms.ChrootForm(buildroot_pkgs=chroot.buildroot_pkgs)
    # FIXME - test if chroot belongs to copr
    if flask.g.user.can_build_in(copr):
        return flask.render_template("coprs/detail/edit_chroot.html",
                                     form=form, copr=copr, chroot=chroot)
    else:
        return page_not_found(
            "You are not allowed to modify chroots in project {0}."
            .format(coprname))


@coprs_ns.route("/<username>/<coprname>/update_chroot/<chrootname>/",
                methods=["POST"])
@login_required
def chroot_update(username, coprname, chrootname):
    form = forms.ChrootForm()
    copr = coprs_logic.CoprsLogic.get(username, coprname).first()
    if not copr:
        return page_not_found(
            "Projec with name {0} does not exist.".format(coprname))

    try:
        chroot = CoprChrootsLogic.get_by_name_safe(copr, chrootname)
    except ValueError as e:
        return page_not_found(str(e))

    if form.validate_on_submit() and flask.g.user.can_build_in(copr):
        if "submit" in flask.request.form:
            action = flask.request.form["submit"]
            if action == "update":
                comps_name = comps_blob = None
                if form.comps.has_file():
                    comps_blob = compress(form.comps.data.stream.read())
                    comps_name = form.comps.data.filename

                coprs_logic.CoprChrootsLogic.update_chroot(
                    flask.g.user, chroot, form.buildroot_pkgs.data,
                    comps=comps_blob, comps_name=comps_name)

            elif action == "delete_comps":
                CoprChrootsLogic.remove_comps(flask.g.user, chroot)

            flask.flash(
                "Buildroot {0} in project {1} has been updated successfully.".format(
                    chrootname, coprname))

            db.session.commit()
        return flask.redirect(flask.url_for("coprs_ns.copr_edit",
                                            username=username,
                                            coprname=copr.name))

    else:
        if form.validate_on_submit():
            flask.flash("You are not allowed to modify chroots.")
        else:
            return chroot_edit(username, coprname, chrootname)


@coprs_ns.route("/<username>/<coprname>/chroot/<chrootname>/comps/")
def chroot_view_comps(username, coprname, chrootname):
    copr = coprs_logic.CoprsLogic.get(username, coprname).first()
    if not copr:
        return page_not_found(
            "Projec with name {0} does not exist.".format(coprname))

    try:
        chroot = CoprChrootsLogic.get_by_name_safe(copr, chrootname)
    except ValueError as e:
        return page_not_found(str(e))

    result = chroot.comps or ""
    return Response(result, mimetype="text/plain; charset=utf-8")
