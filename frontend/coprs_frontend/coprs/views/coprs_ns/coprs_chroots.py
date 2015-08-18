from io import BytesIO
from zlib import compress, decompress

import flask

from coprs import db
from coprs import forms

from coprs.logic import coprs_logic

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
        chroot = coprs_logic.MockChrootsLogic.get_from_name(
            chrootname, active_only=True).first()
    except ValueError as e:
        return page_not_found(str(e))

    if not chroot:
        return page_not_found(
            "Chroot name {0} does not exist.".format(chrootname))

    form = forms.ChrootForm(buildroot_pkgs=copr.buildroot_pkgs(chroot))
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

    #import ipdb; ipdb.set_trace()
    try:
        chroot = coprs_logic.MockChrootsLogic.get_from_name(
            chrootname, active_only=True).first()
    except ValueError as e:
        return page_not_found(str(e))

    if form.validate_on_submit() and flask.g.user.can_build_in(copr):
        # reading comps file if present
        if form.comps.has_file():
            #buffer = form.comps.data.stream.read()

            blob = compress(form.comps.data.stream.read())

            print("LEN: {}".format(len(blob)))
        else:
            blob = None

        coprs_logic.CoprChrootsLogic.update_buildroot_pkgs(
            copr, chroot, form.buildroot_pkgs.data, comps=blob)

        flask.flash(
            "Buildroot {0} for project {1} was updated".format(
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
