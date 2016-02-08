import flask
import json

from flask import url_for
from coprs import db
from coprs import forms
from coprs import helpers
from coprs.models import Package, Build
from coprs.views.coprs_ns import coprs_ns
from coprs.views.coprs_ns.coprs_builds import render_add_build_tito, render_add_build_mock
from coprs.views.misc import login_required, page_not_found, req_with_copr, req_with_copr
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.exceptions import (ActionInProgressException,
                              InsufficientRightsException,)


@coprs_ns.route("/<username>/<coprname>/packages/")
@coprs_ns.route("/g/<group_name>/<coprname>/packages/")
@req_with_copr
def copr_packages(copr):
    packages = PackagesLogic.get_all(copr.id)
    return flask.render_template("coprs/detail/packages.html", packages=packages, copr=copr, empty_build=Build())


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/")
@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/")
@req_with_copr
def copr_package(copr, package_name):
    package = ComplexLogic.get_package_safe(copr, package_name)
    return flask.render_template("coprs/detail/package.html", package=package, copr=copr)


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/rebuild")
@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/rebuild")
@req_with_copr
def copr_rebuild_package(copr, package_name):
    package = ComplexLogic.get_package_safe(copr, package_name)
    data = package.source_json_dict

    if package.source_type_text == "git_and_tito":
        data["git_directory"] = data["git_dir"]  # @FIXME workaround
        form = forms.BuildFormTitoFactory
        f = render_add_build_tito
        view_suffix = "_tito"
    elif package.source_type_text == "mock_scm":
        form = forms.BuildFormMockFactory
        f = render_add_build_mock
        view_suffix = "_mock"
    else:
        flask.flash("Package {} has not the default source which is required for rebuild. Please configure some source"
                    .format(package_name, copr.full_name))
        return flask.redirect(copr_url("coprs_ns.copr_edit_package", copr, package_name=package_name))

    form = form(copr.active_chroots)(data=data)
    return f(copr, form, view="coprs_ns.copr_new_build" + view_suffix, package=package)


@coprs_ns.route("/<username>/<coprname>/package/add")
@coprs_ns.route("/<username>/<coprname>/package/add/<source_type>")
@coprs_ns.route("/g/<group_name>/<coprname>/package/add")
@coprs_ns.route("/g/<group_name>/<coprname>/package/add/<source_type>")
@login_required
@req_with_copr
def copr_add_package(copr, source_type="git_and_tito", **kwargs):
    form = {
        "git_and_tito": forms.PackageFormTito(),
        "mock_scm": forms.PackageFormMock()
    }

    if "form" in kwargs:
        form[kwargs["form"].source_type.data] = kwargs["form"]

    return flask.render_template("coprs/detail/add_package.html", copr=copr, package=None,
                                 source_type=source_type, view="coprs_ns.copr_new_package",
                                 form_tito=form["git_and_tito"], form_mock=form["mock_scm"])


@coprs_ns.route("/<username>/<coprname>/package/new", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/package/new", methods=["POST"])
@login_required
@req_with_copr
def copr_new_package(copr):
    url_on_success = copr_url("coprs_ns.copr_packages", copr)
    return process_save_package(copr, package_name=None, view="coprs_ns.copr_new_package",
                                view_method=copr_add_package, url_on_success=url_on_success)


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/edit")
@coprs_ns.route("/<username>/<coprname>/package/<package_name>/edit/<source_type>")
@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/edit")
@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/edit/<source_type>")
@req_with_copr
def copr_edit_package(copr, package_name, source_type=None, **kwargs):
    package = ComplexLogic.get_package_safe(copr, package_name)
    data = package.source_json_dict
    data["webhook_rebuild"] = package.webhook_rebuild

    if package.source_type and not source_type:
        source_type = package.source_type_text
    elif not source_type:
        source_type = "git_and_tito"

    form_classes = {
        "git_and_tito": forms.PackageFormTito,
        "mock_scm": forms.PackageFormMock,
    }
    form = {k: v(formdata=None) for k, v in form_classes.items()}

    if "form" in kwargs:
        form[kwargs["form"].source_type.data] = kwargs["form"]
    elif package.source_type:
        if package.source_type_text == "git_and_tito" and "git_dir" in data:
            data["git_directory"] = data["git_dir"]  # @FIXME workaround
        form[package.source_type_text] = form_classes[package.source_type_text](data=data)

    return flask.render_template("coprs/detail/package_edit.html", package=package, copr=copr,
                                 source_type=source_type, view="coprs_ns.copr_edit_package",
                                 form_tito=form["git_and_tito"], form_mock=form["mock_scm"])


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/edit", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/edit", methods=["POST"])
@login_required
@req_with_copr
def copr_edit_package_post(copr, package_name):
    url_on_success = copr_url("coprs_ns.copr_packages", copr)
    return process_save_package(copr, package_name, view="coprs_ns.copr_edit_package",
                                view_method=copr_edit_package, url_on_success=url_on_success)


def process_save_package(copr, package_name, view, view_method, url_on_success):
    if flask.request.form["source_type"] == "git_and_tito":
        form = forms.PackageFormTito()
    elif flask.request.form["source_type"] == "mock_scm":
        form = forms.PackageFormMock()
    else:
        raise Exception("Wrong source type")

    if form.validate_on_submit():
        if package_name:
            package = PackagesLogic.get(copr.id, package_name).first()
        else:
            package = PackagesLogic.add(flask.app.g.user, copr, form.package_name.data)

        package.source_type = helpers.BuildSourceEnum(form.source_type.data)
        package.webhook_rebuild = form.webhook_rebuild.data

        if package.source_type == helpers.BuildSourceEnum("git_and_tito"):
            package.source_json = json.dumps({
                "git_url": form.git_url.data,
                "git_branch": form.git_branch.data,
                "git_dir": form.git_directory.data,
                "tito_test": form.tito_test.data})
        elif package.source_type == helpers.BuildSourceEnum("mock_scm"):
            package.source_json = json.dumps({
                "scm_type": form.scm_type.data,
                "scm_url": form.scm_url.data,
                "scm_branch": form.scm_branch.data,
                "spec": form.spec.data})

        try:
            db.session.add(package)
            db.session.commit()
        except (ActionInProgressException, InsufficientRightsException) as e:
            db.session.rollback()
            flask.flash(str(e), "error")
        else:
            flask.flash("Package successfully saved" if package_name else "New package has been created.")

        return flask.redirect(url_on_success)

    return view_method(username=copr.owner.name, coprname=copr.name,
                       package_name=package_name, source_type=form.source_type.data, form=form)


def copr_url(view, copr, **kwargs):
    """
    Examine given copr and generate proper URL for the `view`

    Values of `username/group_name` and `coprname` are automatically passed as the first two URL parameters,
    and therefore you should *not* pass them manually.

    Usage:
      copr_url("coprs_ns.foo", copr)
      copr_url("coprs_ns.foo", copr, arg1='bar', arg2='baz)
    """
    if copr.is_a_group_project:
        return url_for(view, group_name=copr.group.name, coprname=copr.name, **kwargs)
    return url_for(view, username=copr.owner.name, coprname=copr.name, **kwargs)
