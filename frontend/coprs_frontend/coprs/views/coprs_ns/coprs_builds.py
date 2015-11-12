import flask
from flask import request, render_template, url_for
import re
import os
import shutil
import tempfile
import json

from werkzeug import secure_filename

from coprs import app
from coprs import db
from coprs import forms
from coprs import helpers

from coprs.logic import builds_logic
from coprs.logic import coprs_logic
from coprs.logic import packages_logic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic

from coprs.views.misc import login_required, page_not_found, req_with_copr, req_with_copr
from coprs.views.coprs_ns import coprs_ns

from coprs.exceptions import (ActionInProgressException,
                              InsufficientRightsException,)


def url_for_copr_builds(copr):
    if copr.is_a_group_project:
        return url_for("coprs_ns.group_copr_builds",
                       group_name=copr.group.name, coprname=copr.name)
    else:
        return url_for("coprs_ns.copr_builds",
                       username=copr.owner.username, coprname=copr.name)


@coprs_ns.route("/build/<int:build_id>/")
def copr_build_redirect(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    copr = build.copr
    if copr.is_a_group_project:
        return flask.redirect(url_for(
            "coprs_ns.group_copr_build",
            group_name=build.copr.group.name,
            coprname=build.copr.name,
            build_id=build_id))
    else:
        return flask.redirect(url_for(
            "coprs_ns.copr_build",
            username=build.copr.owner.name,
            coprname=build.copr.name,
            build_id=build_id))


def render_copr_build(build_id, copr):
    build = ComplexLogic.get_build_safe(build_id)
    return render_template("coprs/detail/build.html", build=build, copr=copr)


@coprs_ns.route("/<username>/<coprname>/build/<int:build_id>/")
@req_with_copr
def copr_build(copr, build_id):
    return render_copr_build(build_id, copr)


@coprs_ns.route("/g/<group_name>/<coprname>/build/<int:build_id>/")
@req_with_copr
def group_copr_build(copr, build_id):
    return render_copr_build(build_id, copr)


@coprs_ns.route("/<username>/<coprname>/builds/")
@req_with_copr
def copr_builds(copr):
    return render_copr_builds(copr)


@coprs_ns.route("/g/<group_name>/<coprname>/builds/")
@req_with_copr
def group_copr_builds(copr):
    return render_copr_builds(copr)


def render_copr_builds(copr):
    builds_query = builds_logic.BuildsLogic.get_copr_builds_list(copr=copr)
    return flask.render_template("coprs/detail/builds.html",
                                 copr=copr,
                                 builds=builds_query)


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/")
@req_with_copr
def copr_package(copr, package_name):
    return render_package(copr, package_name)


@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/")
@req_with_copr
def group_copr_package(copr, package_name):
    return render_package(copr, package_name)


def render_package(copr, package_name):
    package = ComplexLogic.get_package_safe(copr, package_name)
    return flask.render_template("coprs/detail/package.html", package=package, copr=copr)


@coprs_ns.route("/<username>/<coprname>/add_build/")
@login_required
@req_with_copr
def copr_add_build(copr, form=None):
    return render_add_build(
        copr, form, view='coprs_ns.copr_new_build')

@coprs_ns.route("/g/<group_name>/<coprname>/add_build/")
@login_required
@req_with_copr
def group_copr_add_build(copr, form=None):
    return render_add_build(
        copr, form, view='coprs_ns.group_copr_new_build')

def render_add_build(copr, form, view):
    if not form:
        form = forms.BuildFormFactory.create_form_cls(copr.active_chroots)()
    return flask.render_template("coprs/detail/add_build/url.html",
                                 copr=copr, view=view, form=form)


@coprs_ns.route("/<username>/<coprname>/add_build_upload/")
@login_required
@req_with_copr
def copr_add_build_upload(copr, form=None):
    return render_add_build_upload(
        copr, form, view='coprs_ns.copr_new_build_upload')

@coprs_ns.route("/g/<group_name>/<coprname>/add_build_upload/")
@login_required
@req_with_copr
def group_copr_add_build_upload(copr, form=None):
    return render_add_build_upload(
        copr, form, view='coprs_ns.group_copr_new_build_upload')

def render_add_build_upload(copr, form, view):
    if not form:
        form = forms.BuildFormUploadFactory.create_form_cls(copr.active_chroots)()
    return flask.render_template("coprs/detail/add_build/upload.html",
                                 copr=copr, form=form, view=view)


@coprs_ns.route("/<username>/<coprname>/add_build_tito/")
@login_required
@req_with_copr
def copr_add_build_tito(copr, form=None):
    return render_add_build_tito(
        copr, form, view='coprs_ns.copr_new_build_tito')

@coprs_ns.route("/g/<group_name>/<coprname>/add_build_tito/")
@login_required
@req_with_copr
def group_copr_add_build_tito(copr, form=None):
    return render_add_build_tito(
        copr, form, view='coprs_ns.group_copr_new_build_tito')

def render_add_build_tito(copr, form, view):
    if not form:
        form = forms.BuildFormTitoFactory.create_form_cls(copr.active_chroots)()
    return flask.render_template("coprs/detail/add_build/tito.html",
                                 copr=copr, form=form, view=view)



def process_new_build_tito(copr, add_view, url_on_success):
    form = forms.BuildFormTitoFactory.create_form_cls(copr.active_chroots)()

    if form.validate_on_submit():
        build_options = {
            "enable_net": form.enable_net.data,
            "timeout": form.timeout.data,
        }

        try:
            BuildsLogic.create_new_from_tito(
                flask.g.user, copr, form.git_url.data, form.git_directory.data, form.git_branch.data, form.tito_test.data,
                **build_options
            )
            db.session.commit()
        except (ActionInProgressException, InsufficientRightsException) as e:
            db.session.rollback()
            flask.flash(str(e), "error")
        else:
            flask.flash("New build has been created.")

        return flask.redirect(url_on_success)
    else:
        return render_add_build_upload(copr, form, add_view)


@coprs_ns.route("/<username>/<coprname>/new_build_tito/", methods=["POST"])
@login_required
@req_with_copr
def copr_new_build_tito(copr):
    view = 'coprs_ns.copr_new_build_tito'
    url_on_success = url_for("coprs_ns.copr_builds",
                             username=copr.owner.username, coprname=copr.name)
    return process_new_build_tito(copr, view, url_on_success)


@coprs_ns.route("/g/<group_name>/<coprname>/new_build_tito/", methods=["POST"])
@login_required
@req_with_copr
def group_copr_new_build_tito(copr):
    view = 'coprs_ns.group_copr_new_build_tito'
    url_on_success = url_for("coprs_ns.group_copr_builds",
                             group_name=copr.group.name, coprname=copr.name)
    return process_new_build_tito(copr, view, url_on_success)


@coprs_ns.route("/<username>/<coprname>/add_build_mock/")
@login_required
@req_with_copr
def copr_add_build_mock(copr, form=None):
    return render_add_build_mock(
        copr, form, view='coprs_ns.copr_new_build_mock')


@coprs_ns.route("/g/<group_name>/<coprname>/add_build_mock/")
@login_required
@req_with_copr
def group_copr_add_build_mock(copr, form=None):
    return render_add_build_mock(
        copr, form, view='coprs_ns.group_copr_new_build_mock')


def render_add_build_mock(copr, form, view):
    if not form:
        form = forms.BuildFormMockFactory.create_form_cls(copr.active_chroots)()
    return flask.render_template("coprs/detail/add_build/mock.html",
                                 copr=copr, form=form, view=view)


@coprs_ns.route("/<username>/<coprname>/new_build_mock/", methods=["POST"])
@login_required
@req_with_copr
def copr_new_build_mock(copr):
    view = 'coprs_ns.copr_new_build_mock'
    url_on_success = url_for("coprs_ns.copr_builds",
                             username=copr.owner.username, coprname=copr.name)
    return process_new_build_mock(copr, view, url_on_success)


@coprs_ns.route("/g/<group_name>/<coprname>/new_build_mock/", methods=["POST"])
@login_required
@req_with_copr
def group_copr_new_build_mock(copr):
    view = 'coprs_ns.group_copr_new_build_mock'
    url_on_success = url_for("coprs_ns.group_copr_builds",
                             group_name=copr.group.name, coprname=copr.name)
    return process_new_build_mock(copr, view, url_on_success)


def process_new_build_mock(copr, add_view, url_on_success):
    form = forms.BuildFormMockFactory.create_form_cls(copr.active_chroots)()

    if form.validate_on_submit():
        build_options = {
            "enable_net": form.enable_net.data,
            "timeout": form.timeout.data,
        }

        try:
            BuildsLogic.create_new_from_mock(
                flask.g.user, copr, form.scm_type.data, form.scm_url.data, form.scm_branch.data, form.spec.data,
                **build_options
            )
            db.session.commit()
        except (ActionInProgressException, InsufficientRightsException) as e:
            db.session.rollback()
            flask.flash(str(e), "error")
        else:
            flask.flash("New build has been created.")

        return flask.redirect(url_on_success)
    else:
        return render_add_build_mock(copr, form, add_view)


def process_new_build_upload(copr, add_view, url_on_success):
    form = forms.BuildFormUploadFactory.create_form_cls(copr.active_chroots)()
    if form.validate_on_submit():
        build_options = {
            "enable_net": form.enable_net.data,
            "timeout": form.timeout.data,
        }

        try:
            BuildsLogic.create_new_from_upload(
                flask.g.user, copr,
                f_uploader=lambda path: form.pkgs.data.save(path),
                orig_filename=form.pkgs.data.filename,
                chroot_names=form.selected_chroots,
                **build_options
            )
            db.session.commit()
        except (ActionInProgressException, InsufficientRightsException) as e:
            db.session.rollback()
            flask.flash(str(e), "error")
        else:
            flask.flash("New build has been created.")

        return flask.redirect(url_on_success)
    else:
        return render_add_build_upload(copr, form, add_view)


@coprs_ns.route("/<username>/<coprname>/new_build_upload/", methods=["POST"])
@login_required
@req_with_copr
def copr_new_build_upload(copr):
    view = 'coprs_ns.copr_new_build_upload'
    url_on_success = url_for("coprs_ns.copr_builds",
                             username=copr.owner.username, coprname=copr.name)
    return process_new_build_upload(copr, view, url_on_success)


@coprs_ns.route("/g/<group_name>/<coprname>/new_build_upload/", methods=["POST"])
@login_required
@req_with_copr
def group_copr_new_build_upload(copr):
    view = 'coprs_ns.group_copr_new_build_upload'
    url_on_success = url_for("coprs_ns.group_copr_builds",
                             group_name=copr.group.name, coprname=copr.name)
    return process_new_build_upload(copr, view, url_on_success)


def process_new_build_url(copr, add_view, url_on_success):
    form = forms.BuildFormFactory.create_form_cls(copr.active_chroots)()

    if form.validate_on_submit():
        pkgs = form.pkgs.data.split("\n")

        if not pkgs:
            flask.flash("No builds submitted")
        else:
            # # check which chroots we need
            # chroots = []
            # for chroot in copr.active_chroots:
            #     if chroot.name in form.selected_chroots:
            #         chroots.append(chroot)

            # build each package as a separate build
            try:
                for pkg in pkgs:
                    build_options = {
                        "enable_net": form.enable_net.data,
                        "timeout": form.timeout.data,
                    }
                    BuildsLogic.create_new_from_url(
                        flask.g.user, copr, pkg,
                        chroot_names=form.selected_chroots,
                        **build_options
                    )

            except (ActionInProgressException, InsufficientRightsException) as e:
                flask.flash(str(e), "error")
                db.session.rollback()
            else:
                for pkg in pkgs:
                    flask.flash("New build has been created: {}".format(pkg))

                db.session.commit()

        return flask.redirect(url_on_success)
    else:
        return render_add_build_upload(copr, form, add_view)


@coprs_ns.route("/<username>/<coprname>/new_build/", methods=["POST"])
@login_required
@req_with_copr
def copr_new_build(copr):
    return process_new_build_url(
        copr,
        "coprs_ns.copr_add_build",
        url_on_success=url_for("coprs_ns.copr_builds",
                               username=copr.owner.username, coprname=copr.name)
    )


@coprs_ns.route("/g/<group_name>/<coprname>/new_build/", methods=["POST"])
@login_required
@req_with_copr
def group_copr_new_build(copr):
    return process_new_build_url(
        copr,
        "coprs_ns.group_copr_add_build",
        url_on_success=url_for("coprs_ns.group_copr_builds",
                               group_name=copr.group.name, coprname=copr.name)
    )


def process_rebuild(copr, build_id, view, url_on_success):
    source_build = ComplexLogic.get_build_safe(build_id)
    form = forms.BuildFormRebuildFactory.create_form_cls(copr.active_chroots)()

    if form.validate_on_submit():
        try:
            build_options = {
                "enable_net": form.enable_net.data,
                "timeout": form.timeout.data,
            }

            BuildsLogic.create_new_from_other_build(
                flask.g.user, copr, source_build,
                chroot_names=form.selected_chroots,
                **build_options
            )

        except (ActionInProgressException, InsufficientRightsException) as e:
            flask.flash(str(e), "error")
            db.session.rollback()
        else:
            flask.flash("New build has been created", "success")

            db.session.commit()

        return flask.redirect(url_on_success)
    else:
        return render_add_build(copr, form, view)


@coprs_ns.route("/<username>/<coprname>/new_build_rebuild/<int:build_id>/", methods=["POST"])
@login_required
@req_with_copr
def copr_new_build_rebuild(copr, build_id):

    view='coprs_ns.copr_new_build'
    url_on_success = url_for(
        "coprs_ns.copr_builds",
        username=copr.owner.username, coprname=copr.name)

    return process_rebuild(copr, build_id, view=view, url_on_success=url_on_success)


@coprs_ns.route("/g/<group_name>/<coprname>/new_build_rebuild/<int:build_id>/", methods=["POST"])
@login_required
@req_with_copr
def group_copr_new_build_rebuild(copr, build_id):

    view='coprs_ns.copr_new_build'
    url_on_success = url_for(
        "coprs_ns.copr_builds",
        username=copr.owner.username, coprname=copr.name)

    return process_rebuild(copr, build_id, view=view, url_on_success=url_on_success)


@coprs_ns.route("/<username>/<coprname>/repeat_build/<int:build_id>/",
                methods=["GET", "POST"])
@login_required
@req_with_copr
def copr_repeat_build(copr, build_id):
    return process_copr_repeat_build(build_id, copr)


@coprs_ns.route("/g/<group_name>/<coprname>/repeat_build/<int:build_id>/",
                methods=["GET", "POST"])
@login_required
@req_with_copr
def group_copr_repeat_build(copr, build_id):
    return process_copr_repeat_build(build_id, copr)


def process_copr_repeat_build(build_id, copr):
    build = ComplexLogic.get_build_safe(build_id)
    if not flask.g.user.can_build_in(build.copr):
        flask.flash("You are not allowed to repeat this build.")
    form = forms.BuildFormRebuildFactory.create_form_cls(build.chroots)(
        build_id=build_id, enable_net=build.enable_net,
    )
    # remove all checkboxes by default
    for ch in build.chroots:
        field = getattr(form, ch.name)
        field.data = False
    chroot_to_build = request.args.get("chroot")
    app.logger.debug("got param chroot: {}".format(chroot_to_build))
    if chroot_to_build:
        # set single checkbox if chroot query arg was provided
        if hasattr(form, chroot_to_build):
            getattr(form, chroot_to_build).data = True
    else:
        # set checkbox on the failed chroots
        chroots_to_select = set(ch.name for ch in build.get_chroots_by_status([
            helpers.StatusEnum('failed'), helpers.StatusEnum('canceled'),
        ]))

        for ch in build.chroots:
            if ch.name in chroots_to_select:
                getattr(form, ch.name).data = True
    return flask.render_template(
        "coprs/detail/add_build/rebuild.html",
        copr=copr, build=build, form=form)


def process_cancel_build(build):
    try:
        builds_logic.BuildsLogic.cancel_build(flask.g.user, build)
    except InsufficientRightsException as e:
        flask.flash(str(e), "error")
    else:
        db.session.commit()
        flask.flash("Build {} has been canceled successfully.".format(build.id), "success")
    return flask.redirect(url_for_copr_builds(build.copr))


@coprs_ns.route("/<username>/<coprname>/cancel_build/<int:build_id>/",
                methods=["POST"])
@login_required
def copr_cancel_build(username, coprname, build_id):
    # only the user who ran the build can cancel it
    build = ComplexLogic.get_build_safe(build_id)
    return process_cancel_build(build)


@coprs_ns.route("/g/<group_name>/<coprname>/cancel_build/<int:build_id>/",
                methods=["POST"])
@login_required
def group_copr_cancel_build(group_name, coprname, build_id):
    build = ComplexLogic.get_build_safe(build_id)
    return process_cancel_build(build)


@coprs_ns.route("/<username>/<coprname>/delete_build/<int:build_id>/",
                methods=["POST"])
@login_required
def copr_delete_build(username, coprname, build_id):
    build = ComplexLogic.get_build_safe(build_id)

    try:
        builds_logic.BuildsLogic.delete_build(flask.g.user, build)
    except (InsufficientRightsException, ActionInProgressException) as e:
        flask.flash(str(e), "error")
    else:
        db.session.commit()
        flask.flash("Build has been deleted successfully.", "success")

    return flask.redirect(url_for_copr_builds(build.copr))
