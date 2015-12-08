import flask
import json

from coprs import db
from coprs import forms
from coprs import helpers
from coprs.views.coprs_ns import coprs_ns
from coprs.views.coprs_ns.coprs_builds import render_add_build_tito, render_add_build_mock
from coprs.views.misc import login_required, page_not_found, req_with_copr, req_with_copr
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.packages_logic import PackagesLogic


@coprs_ns.route("/<username>/<coprname>/packages/")
@req_with_copr
def copr_packages(copr):
    return render_packages(copr)


@coprs_ns.route("/g/<group_name>/<coprname>/packages/")
@req_with_copr
def group_copr_packages(copr):
    return render_packages(copr)


def render_packages(copr):
    packages = PackagesLogic.get_all(copr.id)
    return flask.render_template("coprs/detail/packages.html", packages=packages, copr=copr)


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


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/edit")
@req_with_copr
def copr_edit_package(copr, package_name):
    return render_edit_package(copr, package_name, view="coprs_ns.copr_edit_package")


@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/edit")
@req_with_copr
def group_copr_edit_package(copr, package_name):
    return render_edit_package(copr, package_name, view="coprs_ns.copr_edit_package")


def render_edit_package(copr, package_name, view, form_tito=None, form_mock=None):
    package = ComplexLogic.get_package_safe(copr, package_name)

    data = package.source_json_dict
    data["webhook_rebuild"] = package.webhook_rebuild

    if not form_tito:
        if "git_dir" in data:
            data["git_directory"] = data["git_dir"]  # @FIXME workaround
        form_tito = forms.PackageFormTito(data=data)

    if not form_mock:
        form_mock = forms.PackageFormMock(data=data)

    return flask.render_template("coprs/detail/package_edit.html", package=package, copr=copr, form_tito=form_tito,
                                 form_mock=form_mock, view=view)


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/edit", methods=["POST"])
@login_required
@req_with_copr
def copr_edit_package_post(copr, package_name):
    return process_edit_package(copr, package_name, view="coprs_ns.copr_edit_package")


@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/edit", methods=["POST"])
@login_required
@req_with_copr
def group_copr_edit_package_post(copr, package_name):
    return process_edit_package(copr, package_name, view="coprs_ns.copr_edit_package")


def process_edit_package(copr, package_name, view):
    if flask.request.form["source_type"] == "git_and_tito":
        form = forms.PackageFormTito()
        form_var = "form_tito"
    elif flask.request.form["source_type"] == "mock_scm":
        form = forms.PackageFormMock()
        form_var = "form_mock"
    else:
        raise Exception("Wrong source type")

    if form.validate_on_submit():
        package = PackagesLogic.get(copr.id, package_name).first()
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

        db.session.add(package)
        db.session.commit()

    return render_edit_package(copr, package_name, view, **{form_var: form})


@coprs_ns.route("/<username>/<coprname>/package/<package_name>/rebuild")
@req_with_copr
def copr_rebuild_package(copr, package_name):
    return render_copr_rebuild_package(copr, package_name, view="coprs_ns.copr_new_build")


@coprs_ns.route("/g/<group_name>/<coprname>/package/<package_name>/rebuild")
@req_with_copr
def group_copr_rebuild_package(copr, package_name):
    return render_copr_rebuild_package(copr, package_name, view="coprs_ns.copr_new_build")


def render_copr_rebuild_package(copr, package_name, view):
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

    form = form(copr.active_chroots)(data=data)
    return f(copr, form, view=view + view_suffix, package=package)
