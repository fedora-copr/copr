import flask
from flask import Response, render_template

from coprs import db
from coprs import forms
from coprs.exceptions import AccessRestricted

from coprs.logic import coprs_logic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprChrootsLogic
from coprs.views.coprs_ns.coprs_general import url_for_copr_edit

from coprs.views.misc import login_required, req_with_copr, req_with_copr
from coprs.views.coprs_ns import coprs_ns


@coprs_ns.route("/<username>/<coprname>/edit_chroot/<chrootname>/")
@coprs_ns.route("/g/<group_name>/<coprname>/edit_chroot/<chrootname>/")
@login_required
@req_with_copr
def chroot_edit(copr, chrootname):
    """ Route for editing CoprChroot's """
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)
    form = forms.ChrootForm(buildroot_pkgs=chroot.buildroot_pkgs, repos=chroot.repos,
                            module_toggle=chroot.module_toggle, with_opts=chroot.with_opts,
                            without_opts=chroot.without_opts,
                            bootstrap=chroot.bootstrap,
                            bootstrap_image=chroot.bootstrap_image,
                            isolation=chroot.isolation)
    return render_chroot_edit(form, copr, chroot)


def render_chroot_edit(form, copr, chroot):
    """
    Using a pre-filled form, copr and chroot instances, render the
    edit_chroot.html template.
    """

    if flask.g.user.can_edit(copr):
        return render_template("coprs/detail/edit_chroot.html",
                               form=form, copr=copr, chroot=chroot)
    raise AccessRestricted(
        "You are not allowed to modify chroots in project {0}."
        .format(copr.name))


@coprs_ns.route("/<username>/<coprname>/update_chroot/<chrootname>/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/update_chroot/<chrootname>/", methods=["POST"])
@login_required
@req_with_copr
def chroot_update(copr, chrootname):
    chroot_name = chrootname
    form = forms.ChrootForm()
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)

    if not flask.g.user.can_edit(copr):
        raise AccessRestricted(
            "You are not allowed to modify chroots in project {0}."
            .format(copr.name))

    if not form.validate_on_submit():
        flask.flash(form.errors, "error")  # pylint: disable=no-member
        return render_chroot_edit(form, copr, chroot)

    if "submit" in flask.request.form:
        action = flask.request.form["submit"]
        if action == "update":
            comps_name = comps_xml = None

            if form.comps.data:
                comps_xml = form.comps.data.stream.read()
                comps_name = form.comps.data.filename

            coprs_logic.CoprChrootsLogic.update_chroot(
                flask.g.user, chroot,
                form.buildroot_pkgs.data,
                form.repos.data,
                comps=comps_xml, comps_name=comps_name,
                with_opts=form.with_opts.data, without_opts=form.without_opts.data,
                module_toggle=form.module_toggle.data,
                bootstrap=form.bootstrap.data,
                bootstrap_image=form.bootstrap_image.data,
                isolation=form.isolation.data,
            )

        elif action == "delete_comps":
            CoprChrootsLogic.remove_comps(flask.g.user, chroot)

        flask.flash(
            "Buildroot {0} in project {1} has been updated successfully.".format(
                chroot_name, copr.name), 'success')

        db.session.commit()
    return flask.redirect(url_for_copr_edit(copr))


@coprs_ns.route("/<username>/<coprname>/chroot/<chrootname>/comps/")
@coprs_ns.route("/g/<group_name>/<coprname>/chroot/<chrootname>/comps/")
@req_with_copr
def chroot_view_comps(copr, chrootname):
    return render_chroot_view_comps(copr, chrootname)


def render_chroot_view_comps(copr, chroot_name):
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)
    return Response(chroot.comps or "", mimetype="text/plain; charset=utf-8")
