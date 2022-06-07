import flask

from coprs.exceptions import (
        BadRequest,
        ObjectNotFound,
        NoPackageSourceException,
        InsufficientRightsException,
        DuplicateException,
        ApiError,
        UnknownSourceTypeException,
        InvalidForm,
)
from coprs.views.misc import api_login_required
from coprs import db, models, forms, helpers
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic

# @TODO if we need to do this on several places, we should figure a better way to do it
from coprs.views.apiv3_ns.apiv3_builds import to_dict as build_to_dict

from . import query_params, pagination, get_copr, GET, POST, PUT, DELETE, Paginator
from .json2form import get_form_compatible_data


MAX_PACKAGES_WITHOUT_PAGINATION = 10000


def to_dict(package, with_latest_build=False, with_latest_succeeded_build=False):
    source_dict = package.source_json_dict
    if "srpm_build_method" in source_dict:
        source_dict["source_build_method"] = source_dict.pop("srpm_build_method")

    latest = None
    if with_latest_build:
        # If the package was obtained via performance-friendly method
        # `PackagesLogic.get_packages_with_latest_builds_for_dir`,
        # the `package` is still a `models.Package` object but it has one more
        # attribute to it (if the package indeed has at least one build).
        # In such case, the `latest_build` value is already set and using it
        # costs us nothing (no additional SQL query)
        latest = getattr(package, "latest_build", None)

        # If the performance-friendly `latest_build` variable wasn't set because
        # the `package` was obtained differently, e.g. `PackagesLogic.get`, we
        # need to fetch it
        if not latest:
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
        package = PackagesLogic.get(copr.id, packagename)[0]
    except IndexError:
        raise ObjectNotFound("No package with name {name} in copr {copr}".format(name=packagename, copr=copr.name))
    return flask.jsonify(to_dict(package, with_latest_build, with_latest_succeeded_build))


@apiv3_ns.route("/package/list", methods=GET)
@pagination()
@query_params()
def get_package_list(ownername, projectname, with_latest_build=False,
                     with_latest_succeeded_build=False, **kwargs):

    with_latest_build = get_arg_to_bool(with_latest_build)
    with_latest_succeeded_build = get_arg_to_bool(with_latest_succeeded_build)

    copr = get_copr(ownername, projectname)
    query = PackagesLogic.get_all(copr.id)
    paginator = Paginator(query, models.Package, **kwargs)
    packages = paginator.get().all()

    if len(packages) > MAX_PACKAGES_WITHOUT_PAGINATION:
        raise ApiError("Too many packages, please use pagination. "
                       "Requests are limited to only {0} packages at once."
                       .format(MAX_PACKAGES_WITHOUT_PAGINATION))

    # Query latest builds for all packages at once. We can't use this solution
    # for querying latest successfull builds, so that will be a little slower
    if with_latest_build:
        packages = PackagesLogic.get_packages_with_latest_builds_for_dir(
            copr.main_dir,
            small_build=False,
            packages=packages)

    items = [to_dict(p, with_latest_build, with_latest_succeeded_build)
             for p in packages]
    return flask.jsonify(items=items, meta=paginator.meta)


@apiv3_ns.route("/package/add/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=POST)
@api_login_required
def package_add(ownername, projectname, package_name, source_type_text):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
    process_package_add_or_edit(copr, source_type_text, data=data)
    package = PackagesLogic.get(copr.id, package_name).first()
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/edit/<ownername>/<projectname>/<package_name>/<source_type_text>", methods=PUT)
@api_login_required
def package_edit(ownername, projectname, package_name, source_type_text=None):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
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
    data = rename_fields(get_form_compatible_data(
        preserve=["python_versions", "chroots", "exclude_chroots"]))
    form = forms.RebuildPackageFactory.create_form_cls(copr.active_chroots)(data, meta={'csrf': False})
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
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
        raise InvalidForm(form)
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


def process_package_add_or_edit(copr, source_type_text, package=None, data=None):
    if not flask.g.user.can_edit(copr):
        raise InsufficientRightsException(
            "You are not allowed to add or edit packages in this copr.")

    formdata = data or flask.request.form
    try:
        if package and data:
            formdata = data.copy()
            for key in package.source_json_dict.keys() - data.keys():
                value = package.source_json_dict[key]
                add_function = formdata.setlist if type(value) == list else formdata.add
                add_function(key, value)
        form = forms.get_package_form_cls_by_source_type_text(source_type_text)(formdata, meta={'csrf': False})
    except UnknownSourceTypeException:
        raise ApiError("Unsupported package source type {source_type_text}".format(source_type_text=source_type_text))

    if form.validate_on_submit():
        if not package:
            try:
                package = PackagesLogic.add(flask.app.g.user, copr, form.package_name.data)
            except InsufficientRightsException:
                raise ApiError("Insufficient permissions.")
            except DuplicateException:
                raise ApiError("Package {0} already exists in copr {1}.".format(form.package_name.data, copr.full_name))

        try:
            source_type = helpers.BuildSourceEnum(source_type_text)
        except KeyError:
            source_type = helpers.BuildSourceEnum("scm")

        package.source_type = source_type
        package.source_json = form.source_json
        if "webhook_rebuild" in formdata:
            package.webhook_rebuild = form.webhook_rebuild.data
        if "max_builds" in formdata:
            package.max_builds = form.max_builds.data
        if "chroot_denylist" in formdata:
            package.chroot_denylist_raw = form.chroot_denylist.data

        PackagesLogic.log_being_admin(flask.g.user, package)
        db.session.add(package)
        db.session.commit()
    else:
        raise ApiError(form.errors)

    return flask.jsonify({
        "output": "ok",
        "message": "Create or edit operation was successful.",
        "package": package.to_dict(),
    })
