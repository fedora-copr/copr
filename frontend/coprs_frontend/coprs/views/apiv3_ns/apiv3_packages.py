import flask

from coprs.exceptions import (
        BadRequest,
        ObjectNotFound,
        NoPackageSourceException
)
from coprs.views.misc import api_login_required
from coprs import db, models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic

# @TODO if we need to do this on several places, we should figure a better way to do it
from coprs.views.apiv3_ns.apiv3_builds import to_dict as build_to_dict

# @TODO Don't import things from APIv1
from coprs.views.api_ns.api_general import process_package_add_or_edit

from . import query_params, pagination, get_copr, ListPaginator, GET, POST, PUT, DELETE
from .json2form import get_form_compatible_data

def to_dict(package, with_latest_build=False, with_latest_succeeded_build=False):
    source_dict = package.source_json_dict
    if "srpm_build_method" in source_dict:
        source_dict["source_build_method"] = source_dict.pop("srpm_build_method")

    latest = None
    if with_latest_build:
        latest = package.last_build()
        latest = build_to_dict(latest) if latest else None

    latest_succeeded = None
    if with_latest_succeeded_build:
        latest_succeeded = package.last_build(successful=True)
        latest_succeeded = build_to_dict(latest_succeeded) if latest_succeeded else None

    return {
        "id": package.id,
        "name": package.name,
        "projectname": package.copr.name,
        "ownername": package.copr.owner_name,
        "source_type": package.source_type_text,
        "source_dict": source_dict,
        "auto_rebuild": package.webhook_rebuild,
        "builds": {
            "latest": latest,
            "latest_succeeded": latest_succeeded,
        }
    }


def rename_fields(input):
    replace = {
        "is_background": "background",
        "memory_limit": "memory_reqs",
        "source_build_method": "srpm_build_method",
        "script_builddeps": "builddeps",
        "script_resultdir": "resultdir",
        "script_chroot": "chroot",
    }
    output = input.copy()
    for from_name, to_name in replace.items():
        if from_name not in output:
            continue
        output[to_name] = output.pop(from_name)
    return output


def get_arg_to_bool(argument):
    """
    Through GET, we send requests like '/?with_latest_build=True', so the
    argument is passed down as "string".  But by default, as function argument,
    the value may be boolean, too.
    """
    if not argument:
        return argument
    if argument in [True, "True", "true", 1, "1"]:
        return True
    return False


@apiv3_ns.route("/package", methods=GET)
@query_params()
def get_package(ownername, projectname, packagename,
                with_latest_build=False, with_latest_succeeded_build=False):
    with_latest_build = get_arg_to_bool(with_latest_build)
    with_latest_succeeded_build = get_arg_to_bool(with_latest_succeeded_build)

    copr = get_copr(ownername, projectname)
    try:
        package = PackagesLogic.get(copr.main_dir.id, packagename)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}".format(name=packagename, copr=copr.name))
    return flask.jsonify(to_dict(package, with_latest_build, with_latest_succeeded_build))


@apiv3_ns.route("/package/list/", methods=GET)
@pagination()
@query_params()
def get_package_list(ownername, projectname, with_latest_build=False,
                     with_latest_succeeded_build=False, **kwargs):

    with_latest_build = get_arg_to_bool(with_latest_build)
    with_latest_succeeded_build = get_arg_to_bool(with_latest_succeeded_build)

    copr = get_copr(ownername, projectname)
    packages = PackagesLogic.get_packages_with_latest_builds_for_dir(copr.main_dir.id, small_build=False)
    paginator = ListPaginator(packages, models.Package, **kwargs)

    packages = paginator.map(lambda x: to_dict(x, with_latest_build, with_latest_succeeded_build))
    return flask.jsonify(items=packages, meta=paginator.meta)


@apiv3_ns.route("/package/add/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=POST)
@api_login_required
def package_add(ownername, projectname, package_name, source_type_text):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
    process_package_add_or_edit(copr, source_type_text, data=data)
    package = PackagesLogic.get(copr.main_dir.id, package_name).first()
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/edit/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=PUT)
@api_login_required
def package_edit(ownername, projectname, package_name, source_type_text=None):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
    try:
        package = PackagesLogic.get(copr.main_dir.id, package_name)[0]
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
        package = PackagesLogic.get(copr.main_dir.id, form.package_name.data)[0]
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
    data = rename_fields(get_form_compatible_data(
        preserve=["python_versions", "chroots", "exclude_chroots"]))
    form = forms.RebuildPackageFactory.create_form_cls(copr.active_chroots)(data, meta={'csrf': False})
    try:
        package = PackagesLogic.get(copr.main_dir.id, form.package_name.data)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))
    if form.validate_on_submit():
        buildopts = {k: v for k, v in form.data.items() if k in data}
        try:
            build = PackagesLogic.build_package(
                flask.g.user, copr, package, form.selected_chroots,
                copr_dirname=form.project_dirname.data, **buildopts)
        except NoPackageSourceException as e:
            raise BadRequest(str(e))
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
        package = PackagesLogic.get(copr.main_dir.id, form.package_name.data)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))

    PackagesLogic.delete_package(flask.g.user, package)
    db.session.commit()
    return flask.jsonify(to_dict(package))
