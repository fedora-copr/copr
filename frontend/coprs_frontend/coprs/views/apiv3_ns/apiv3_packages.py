# All documentation is to be written on method-level because then it is
# recognized by flask-restx and rendered in Swagger
# pylint: disable=missing-class-docstring

import flask
from flask_restx import Namespace, Resource

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
from coprs.views.apiv3_ns import (
    api,
    rename_fields_helper,
    query_to_parameters,
    pagination,
    deprecated_route_method_type,
)
from coprs.views.apiv3_ns.schema.schemas import (
    package_model,
    package_get_params,
    package_add_input_model,
    package_edit_input_model,
    package_get_list_params,
    pagination_package_model,
    build_model,
    base_package_input_model,
)
from coprs.views.apiv3_ns.schema.docs import add_package_docs, edit_package_docs
from coprs.logic.packages_logic import PackagesLogic

# @TODO if we need to do this on several places, we should figure a better way to do it
from coprs.views.apiv3_ns.apiv3_builds import to_dict as build_to_dict

from . import get_copr, Paginator
from .json2form import get_form_compatible_data


MAX_PACKAGES_WITHOUT_PAGINATION = 10000


apiv3_packages_ns = Namespace("package", description="Packages")
api.add_namespace(apiv3_packages_ns)


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


def rename_fields(input_dict):
    return rename_fields_helper(input_dict, {
        "is_background": "background",
        "memory_limit": "memory_reqs",
        "source_build_method": "srpm_build_method",
        "script_builddeps": "builddeps",
        "script_resultdir": "resultdir",
        "script_chroot": "chroot",
    })


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


@apiv3_packages_ns.route("/")
class GetPackage(Resource):
    @query_to_parameters
    @apiv3_packages_ns.doc(params=package_get_params)
    @apiv3_packages_ns.marshal_with(package_model)
    def get(self, ownername, projectname, packagename, with_latest_build=False,
            with_latest_succeeded_build=False):
        """
        Get a package
        Get a single package from a Copr project.
        """
        copr = get_copr(ownername, projectname)
        try:
            package = PackagesLogic.get(copr.id, packagename)[0]
        except IndexError as ex:
            msg = ("No package with name {name} in copr {copr}"
                   .format(name=packagename, copr=copr.name))
            raise ObjectNotFound(msg) from ex
        return to_dict(package, with_latest_build, with_latest_succeeded_build)


@apiv3_packages_ns.route("/list")
class PackageGetList(Resource):
    @pagination
    @query_to_parameters
    @apiv3_packages_ns.doc(params=package_get_list_params)
    @apiv3_packages_ns.marshal_with(pagination_package_model)
    def get(self, ownername, projectname, with_latest_build=False,
            with_latest_succeeded_build=False, **kwargs):
        """
        Get a list of packages
        Get a list of packages from a Copr project
        """
        with_latest_build = get_arg_to_bool(with_latest_build)
        with_latest_succeeded_build = get_arg_to_bool(with_latest_succeeded_build)

        copr = get_copr(ownername, projectname)
        query = PackagesLogic.get_all(copr.id)
        paginator = Paginator(query, models.Package, **kwargs)
        packages = paginator.get().all()

        if len(packages) > MAX_PACKAGES_WITHOUT_PAGINATION:
            raise ApiError("Too many packages, please use pagination. "
                           "Requests are limited to only {0} packages at once."
                           .format(MAX_PACKAGES_WITHOUT_PAGINATION), 413)

        # Query latest builds for all packages at once. We can't use this solution
        # for querying latest successfull builds, so that will be a little slower
        if with_latest_build:
            packages = PackagesLogic.get_packages_with_latest_builds_for_dir(
                copr.main_dir,
                small_build=False,
                packages=packages)

        items = [to_dict(p, with_latest_build, with_latest_succeeded_build)
                 for p in packages]
        return {"items": items, "meta": paginator.meta}


@apiv3_packages_ns.route("/add/<ownername>/<projectname>/<package_name>/<source_type_text>")
class PackageAdd(Resource):
    @api_login_required
    @apiv3_packages_ns.doc(params=add_package_docs)
    @apiv3_packages_ns.expect(package_add_input_model)
    @apiv3_packages_ns.marshal_with(package_model)
    def post(self, ownername, projectname, package_name, source_type_text):
        """
        Create a package
        Create a new package inside a specified Copr project.

        See what fields are required for which source types:
        https://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        """
        copr = get_copr(ownername, projectname)
        data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
        process_package_add_or_edit(copr, source_type_text, data=data)
        package = PackagesLogic.get(copr.id, package_name).first()
        return to_dict(package)


@apiv3_packages_ns.route("/edit/<ownername>/<projectname>/<package_name>/")
@apiv3_packages_ns.route("/edit/<ownername>/<projectname>/<package_name>/<source_type_text>")
class PackageEdit(Resource):
    @api_login_required
    @apiv3_packages_ns.doc(params=edit_package_docs)
    @apiv3_packages_ns.expect(package_edit_input_model)
    @apiv3_packages_ns.marshal_with(package_model)
    def post(self, ownername, projectname, package_name, source_type_text=None):
        """
        Edit a package
        Edit an existing package within a Copr project.

        See what fields are required for which source types:
        https://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html
        """
        copr = get_copr(ownername, projectname)
        data = rename_fields(get_form_compatible_data(preserve=["python_versions"]))
        try:
            package = PackagesLogic.get(copr.id, package_name)[0]
            source_type_text = source_type_text or package.source_type_text
        except IndexError as ex:
            msg = ("Package {name} does not exists in copr {copr}."
                   .format(name=package_name, copr=copr.full_name))
            raise ObjectNotFound(msg) from ex

        process_package_add_or_edit(copr, source_type_text, package=package, data=data)
        return to_dict(package)


@apiv3_packages_ns.route("/reset")
class PackageReset(Resource):
    @staticmethod
    def _common():
        copr = get_copr()
        form = forms.BasePackageForm()
        try:
            package = PackagesLogic.get(copr.id, form.package_name.data)[0]
        except IndexError as exc:
            raise ObjectNotFound(
                "No package with name {name} in copr {copr}".format(
                    name=form.package_name.data, copr=copr.name
                )
            ) from exc

        PackagesLogic.reset_package(flask.g.user, package)
        db.session.commit()
        return to_dict(package)

    @api_login_required
    @apiv3_packages_ns.marshal_with(package_model)
    @apiv3_packages_ns.expect(base_package_input_model)
    def put(self):
        """
        Reset a package
        Reset a package to its initial state.
        """
        return self._common()

    @deprecated_route_method_type(apiv3_packages_ns, "POST", "PUT")
    @api_login_required
    @apiv3_packages_ns.marshal_with(package_model)
    @apiv3_packages_ns.expect(base_package_input_model)
    def post(self):
        """
        Reset a package
        Reset a package to its initial state.
        """
        return self._common()


@apiv3_packages_ns.route("/build")
class PackageBuild(Resource):
    @api_login_required
    @apiv3_packages_ns.marshal_with(build_model)
    def post(self):
        """
        Build a package
        Build a package in a Copr project.
        """
        copr = get_copr()
        data = rename_fields(get_form_compatible_data(
            preserve=["python_versions", "chroots", "exclude_chroots"]))
        form = forms.RebuildPackageFactory.create_form_cls(copr.active_chroots)(data, meta={'csrf': False})
        try:
            package = PackagesLogic.get(copr.id, form.package_name.data)[0]
        except IndexError as exc:
            raise ObjectNotFound(
                "No package with name {name} in copr {copr}".format(
                    name=form.package_name.data, copr=copr.name
                )
            ) from exc
        if form.validate_on_submit():
            buildopts = {k: v for k, v in form.data.items() if k in data}
            try:
                build = PackagesLogic.build_package(
                    flask.g.user, copr, package, form.selected_chroots,
                    copr_dirname=form.project_dirname.data, **buildopts)
            except NoPackageSourceException as e:
                raise BadRequest(str(e)) from e
            db.session.commit()
        else:
            raise InvalidForm(form)
        return build_to_dict(build)


@apiv3_packages_ns.route("/delete")
class PackageDelete(Resource):
    @staticmethod
    def _common():
        copr = get_copr()
        form = forms.BasePackageForm()
        try:
            package = PackagesLogic.get(copr.id, form.package_name.data)[0]
        except IndexError as exc:
            raise ObjectNotFound(
                "No package with name {name} in copr {copr}".format(
                    name=form.package_name.data, copr=copr.name
                )
            ) from exc

        PackagesLogic.delete_package(flask.g.user, package)
        db.session.commit()
        return to_dict(package)

    @api_login_required
    @apiv3_packages_ns.marshal_with(package_model)
    @apiv3_packages_ns.expect(base_package_input_model)
    def delete(self):
        """
        Delete a package
        Delete a package from a Copr project.
        """
        return self._common()

    @deprecated_route_method_type(apiv3_packages_ns, "POST", "DELETE")
    @api_login_required
    @apiv3_packages_ns.marshal_with(package_model)
    @apiv3_packages_ns.expect(base_package_input_model)
    def post(self):
        """
        Delete a package
        Delete a package from a Copr project.
        """
        return self._common()


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
    except UnknownSourceTypeException as ex:
        msg = ("Unsupported package source type {source_type_text}"
               .format(source_type_text=source_type_text))
        raise ApiError(msg, 400) from ex

    if form.validate_on_submit():
        if not package:
            try:
                package = PackagesLogic.add(flask.app.g.user, copr, form.package_name.data)
            except InsufficientRightsException as ex:
                raise ApiError("Insufficient permissions.", 403) from ex
            except DuplicateException as ex:
                msg = ("Package {0} already exists in copr {1}."
                       .format(form.package_name.data, copr.full_name))
                raise ApiError(msg, 409) from ex

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
        if "timeout" in formdata:
            package.timeout = form.timeout.data
        if "chroot_denylist" in formdata:
            package.chroot_denylist_raw = form.chroot_denylist.data

        PackagesLogic.log_being_admin(flask.g.user, package)
        db.session.add(package)
        db.session.commit()
    else:
        raise InvalidForm(form)

    return flask.jsonify({
        "output": "ok",
        "message": "Create or edit operation was successful.",
        "package": package.to_dict(),
    })
