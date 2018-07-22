import flask
import wtforms
from . import query_params, pagination, get_copr, Paginator, GET, POST, PUT, DELETE
from .json2form import get_form_compatible_data, get_input
from coprs.exceptions import ApiError
from coprs.exceptions import (ApiError, InsufficientRightsException, ActionInProgressException,
                              NoPackageSourceException, ObjectNotFound, BadRequest)
from coprs.views.misc import api_login_required
from coprs import db, models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic

# @TODO if we need to do this on several places, we should figure a better way to do it
from coprs.views.apiv3_ns.apiv3_builds import to_dict as build_to_dict

# @TODO Don't import things from APIv1
from coprs.views.api_ns.api_general import process_package_add_or_edit


def to_dict(package):
    source_dict = package.source_json_dict
    source_dict["source_build_method"] = source_dict.pop("srpm_build_method", None)
    return {
        "id": package.id,
        "name": package.name,
        "projectname": package.copr.name,
        "ownername": package.copr.owner_name,
        "source_type": package.source_type_text,
        "source_dict": source_dict,
        "auto_rebuild": package.webhook_rebuild,
    }


def rename_fields(input):
    replace = {
        "is_background": "background",
        "memory_limit": "memory_reqs",
        "source_build_method": "srpm_build_method",
    }
    output = input.copy()
    for from_name, to_name in replace.items():
        if from_name not in output:
            continue
        output[to_name] = output.pop(from_name)
    return output


@apiv3_ns.route("/package", methods=GET)
@query_params()
def get_package(ownername, projectname, packagename):
    copr = get_copr(ownername, projectname)
    try:
        package = PackagesLogic.get(copr.id, packagename)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}".format(name=packagename, copr=copr.name))
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/list/", methods=GET)
@pagination()
@query_params()
def get_package_list(ownername, projectname, **kwargs):
    copr = get_copr(ownername, projectname)
    paginator = Paginator(PackagesLogic.get_all(copr.id), models.Package, **kwargs)
    packages = paginator.map(to_dict)
    return flask.jsonify(items=packages, meta=paginator.meta)


@apiv3_ns.route("/package/add/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=POST)
@api_login_required
def package_add(ownername, projectname, package_name, source_type_text):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_input())
    process_package_add_or_edit(copr, source_type_text, data=data)
    package = PackagesLogic.get(copr.id, package_name).first()
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/edit/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=PUT)
@api_login_required
def package_edit(ownername, projectname, package_name, source_type_text=None):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_input())
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
        source_type_text = source_type_text or package.source_type_text
    except IndexError:
        raise ObjectNotFound("Package {name} does not exists in copr {copr}."
                             .format(name=package_name, copr=copr.full_name))

    process_package_add_or_edit(copr, source_type_text, package=package, data=data)
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/reset", methods=PUT)
@api_login_required
def package_reset():
    copr = get_copr()
    form = forms.BasePackageForm()
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))

    PackagesLogic.reset_package(flask.g.user, package)
    db.session.commit()
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/build", methods=POST)
@api_login_required
def package_build():
    copr = get_copr()
    data = rename_fields(get_form_compatible_data())
    form = forms.RebuildPackageFactory.create_form_cls(copr.active_chroots)(data, csrf_enabled=False)
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))
    if form.validate_on_submit():
        buildopts = {k: v for k, v in form.data.items() if k in data}
        build = PackagesLogic.build_package(flask.g.user, copr, package, form.selected_chroots, **buildopts)
        db.session.commit()
    else:
        raise BadRequest(form.errors)
    return flask.jsonify(build_to_dict(build))


@apiv3_ns.route("/package/delete", methods=DELETE)
@api_login_required
def package_delete():
    copr = get_copr()
    form = forms.BasePackageForm()
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))

    PackagesLogic.delete_package(flask.g.user, package)
    db.session.commit()
    return flask.jsonify(to_dict(package))
