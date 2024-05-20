# All documentation is to be written on method-level because then it is
# recognized by flask-restx and rendered in Swagger
# pylint: disable=missing-class-docstring

import os
import flask
from sqlalchemy.orm import joinedload

from werkzeug.datastructures import MultiDict
from werkzeug.utils import secure_filename
from flask_restx import Namespace, Resource

from copr_common.enums import StatusEnum
from coprs import db, forms, models
from coprs.exceptions import (BadRequest, AccessRestricted)
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import api, rename_fields_helper, deprecated_route_method_type
from coprs.views.apiv3_ns.schema.schemas import build_model, pagination_build_model, source_chroot_model, \
    source_build_config_model, list_build_params, create_build_url_input_model, create_build_upload_input_model, \
    create_build_scm_input_model, create_build_distgit_input_model, create_build_pypi_input_model, \
    create_build_rubygems_input_model, create_build_custom_input_model, delete_builds_input_model, list_build_model
from coprs.views.apiv3_ns.schema.docs import get_build_docs
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.coprs_logic import CoprDirsLogic

from . import (
    get_copr,
    SubqueryPaginator,
    json2form,
    query_to_parameters,
    pagination,
    file_upload,
)
from .json2form import get_form_compatible_data


apiv3_builds_ns = Namespace("build", description="Builds")
api.add_namespace(apiv3_builds_ns)


def to_dict(build):
    return {
        "id": build.id,
        "state": build.state,
        "projectname": build.copr.name,
        "ownername": build.copr.owner_name,
        "repo_url": build.copr.repo_url,
        "source_package": {"name": build.package_name, "version": build.pkg_version, "url": build.srpm_url},
        "submitted_on": build.submitted_on,
        "started_on": build.min_started_on,
        "ended_on": build.max_ended_on,
        "submitter": build.user.name if build.user else None,
        "chroots": [chroot.name for chroot in build.build_chroots],
        "project_dirname": build.copr_dir.name,
        "is_background": build.is_background,
    }


def to_source_chroot(build):
    return {
        "state": StatusEnum(build.source_status),
        "result_url": os.path.dirname(build.source_live_log_url),
        #  @TODO Do we have such information stored?
        # "started_on": None,
        # "ended_on": None
    }


def to_source_build_config(build):
    return {
        "source_type": build.source_type_text,
        "source_dict": build.source_json_dict,
        "memory_limit": build.memory_reqs,
        "timeout": build.timeout,
        "is_background": build.is_background,
    }


def rename_fields(input_dict):
    return rename_fields_helper(input_dict, {
        "source_build_method": "srpm_build_method",
    })


def process_creating_new_build(copr, form, create_new_build):
    if not form.validate_on_submit():
        raise BadRequest("Bad request parameters: {0}".format(form.errors))

    if not flask.g.user.can_build_in(copr):
        raise AccessRestricted("User {} is not allowed to build in the copr: {}"
                               .format(flask.g.user.username, copr.full_name))
    form.isolation.data = "unchanged" if form.isolation.data is None else form.isolation.data

    generic_build_options = {
        'chroot_names': form.selected_chroots,
        'background': form.background.data,
        'copr_dirname': form.project_dirname.data,
        'timeout': form.timeout.data,
        'bootstrap': form.bootstrap.data,
        'isolation': form.isolation.data,
        'after_build_id': form.after_build_id.data,
        'with_build_id': form.with_build_id.data,
        'packit_forge_project': form.packit_forge_project.data
    }

    if form.enable_net.data is not None:
        generic_build_options['enable_net'] = form.enable_net.data

    # From URLs it can be created multiple builds at once
    # so it can return a list
    build = create_new_build(generic_build_options)
    db.session.commit()

    if type(build) == list:
        builds = [build] if type(build) != list else build
        return {"items": [to_dict(b) for b in builds], "meta": {}}

    return to_dict(build)


@apiv3_builds_ns.route("/<int:build_id>")
class GetBuild(Resource):
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(build_model)
    def get(self, build_id):
        """
        Get a build
        Get details for a single Copr build.
        """
        build = ComplexLogic.get_build(build_id)
        result = to_dict(build)

        # TODO: I think this workaround is bad usage of models... check it later
        # Workaround - `marshal_with` needs the input `build_id` to be present
        # in the returned dict. Don't worry, it won't get to the end user, it
        # will be stripped away.
        result["build_id"] = result["id"]
        return result


@apiv3_builds_ns.route("/list")
class ListBuild(Resource):
    @pagination
    @query_to_parameters
    @apiv3_builds_ns.doc(params=list_build_params)
    @apiv3_builds_ns.marshal_with(pagination_build_model)
    def get(self, ownername, projectname, packagename=None, status=None, **kwargs):
        """
        List builds
        List all builds in a Copr project.
        """
        copr = get_copr(ownername, projectname)

        # WORKAROUND
        # We can't filter builds by status directly in the database, because we
        # use a logic in Build.status property to determine a build status.
        # Therefore if we want to filter by `status`, we need to query all builds
        # and filter them in the application and then return the desired number.
        limit = kwargs["limit"]
        paginator_limit = None if status else kwargs["limit"]
        del kwargs["limit"]

        # Loading relationships straight away makes running `to_dict` somewhat
        # faster, which adds up over time, and  brings a significant speedup for
        # large projects
        query = BuildsLogic.get_multiple()
        query = query.options(
            joinedload(models.Build.build_chroots),
            joinedload(models.Build.package),
            joinedload(models.Build.copr),
        )

        subquery = query.filter(models.Build.copr == copr)
        if packagename:
            subquery = BuildsLogic.filter_by_package_name(subquery, packagename)

        paginator = SubqueryPaginator(query, subquery, models.Build, limit=paginator_limit, **kwargs)

        builds = paginator.map(to_dict)

        if status:
            builds = [b for b in builds if b["state"] == status][:limit]
            paginator.limit = limit

        return {"items": builds, "meta": paginator.meta}


@apiv3_builds_ns.route("/source-log/<int:build_id>")
class SourceChroot(Resource):
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(source_chroot_model)
    def get(self, build_id):
        """
        Get source chroot
        Get source chroot for a build.
        """
        build = ComplexLogic.get_build(build_id)
        return to_source_chroot(build)


@apiv3_builds_ns.route("/source-build-config/<int:build_id>")
class SourceBuildConfig(Resource):
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(source_build_config_model)
    def get(self, build_id):
        """
        Get source build config
        Get source build config for a build.
        """
        build = ComplexLogic.get_build(build_id)
        return to_source_build_config(build)


@apiv3_builds_ns.route("/built-packages/<int:build_id>")
class BuildPackages(Resource):
    @apiv3_builds_ns.doc(
        params=get_build_docs,
        # not marshalable b/c the dict key is dynamic
        responses={200: '{"chroot_name": any_result_dict_or_value}'}
    )
    def get(self, build_id):
        """
        Get built packages
        Get built packages (NEVRA dicts) for a given build
        """
        build = ComplexLogic.get_build(build_id)
        return build.results_dict


@apiv3_builds_ns.route("/cancel/<int:build_id>")
class CancelBuild(Resource):
    @staticmethod
    def _common(build_id):
        build = ComplexLogic.get_build(build_id)
        BuildsLogic.cancel_build(flask.g.user, build)
        db.session.commit()
        return to_dict(build)

    @api_login_required
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(build_model)
    def put(self, build_id):
        """
        Cancel a build
        Cancel a build by its id.
        """
        return self._common(build_id)

    @api_login_required
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(build_model)
    @deprecated_route_method_type(apiv3_builds_ns, "POST", "PUT")
    def post(self, build_id):
        """
        Cancel a build
        Cancel a build by its id.
        """
        return self._common(build_id)


@apiv3_builds_ns.route("/create/url")
class CreateFromUrl(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_url_input_model)
    @apiv3_builds_ns.marshal_with(pagination_build_model)
    def post(self):
        """
        Create a build from URL
        Create a build from a URL.
        """
        copr = get_copr()
        data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
        # pylint: disable-next=not-callable
        form = forms.BuildFormUrlFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            # create separate build for each package
            pkgs = form.pkgs.data.split("\n")
            return [BuildsLogic.create_new_from_url(
                flask.g.user, copr,
                url=pkg,
                **options,
            ) for pkg in pkgs]

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/upload")
class CreateFromUpload(Resource):
    @file_upload
    @api_login_required
    @apiv3_builds_ns.expect(create_build_upload_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build from upload
        Create a build from an uploaded file.
        """
        copr = get_copr()
        data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
        # pylint: disable-next=not-callable
        form = forms.BuildFormUploadFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            return BuildsLogic.create_new_from_upload(
                flask.g.user, copr,
                form.pkgs,
                orig_filename=secure_filename(form.pkgs.data.filename),
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/scm")
class CreateFromScm(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_scm_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build from SCM
        Create a build from a source code management system.
        """
        copr = get_copr()
        data = rename_fields(get_form_compatible_data(preserve=["chroots", "exclude_chroots"]))
        # pylint: disable-next=not-callable
        form = forms.BuildFormScmFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            return BuildsLogic.create_new_from_scm(
                flask.g.user,
                copr,
                scm_type=form.scm_type.data,
                clone_url=form.clone_url.data,
                committish=form.committish.data,
                subdirectory=form.subdirectory.data,
                spec=form.spec.data,
                srpm_build_method=form.srpm_build_method.data,
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/distgit")
class CreateFromDistGit(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_distgit_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build from DistGit
        Create a build from a DistGit repository.
        """
        copr = get_copr()
        data = rename_fields(get_form_compatible_data(preserve=["chroots", "exclude_chroots"]))
        # pylint: disable-next=not-callable
        form = forms.BuildFormDistGitSimpleFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            return BuildsLogic.create_new_from_distgit(
                flask.g.user,
                copr,
                package_name=form.package_name.data,
                distgit_name=form.distgit.data,
                distgit_namespace=form.namespace.data,
                committish=form.committish.data,
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/pypi")
class CreateFromPyPi(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_pypi_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build from PyPi
        Create a build from a PyPi package.
        """
        copr = get_copr()
        data = MultiDict(json2form.without_empty_fields(json2form.get_input()))
        # pylint: disable-next=not-callable
        form = forms.BuildFormPyPIFactory(copr.active_chroots)(data, meta={'csrf': False})

        # TODO: automatically prepopulate all form fields with their defaults
        if not form.python_versions.data:
            form.python_versions.data = form.python_versions.default

        def create_new_build(options):
            return BuildsLogic.create_new_from_pypi(
                flask.g.user,
                copr,
                form.pypi_package_name.data,
                form.pypi_package_version.data,
                form.spec_generator.data,
                form.spec_template.data,
                form.python_versions.data,
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/rubygems")
class CreateFromRubyGems(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_rubygems_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build from RubyGems
        Create a build from a RubyGems package.
        """
        copr = get_copr()
        data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
        # pylint: disable-next=not-callable
        form = forms.BuildFormRubyGemsFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            return BuildsLogic.create_new_from_rubygems(
                flask.g.user,
                copr,
                form.gem_name.data,
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/create/custom")
class CreateCustom(Resource):
    @api_login_required
    @apiv3_builds_ns.expect(create_build_custom_input_model)
    @apiv3_builds_ns.marshal_with(build_model)
    def post(self):
        """
        Create a build using custom method
        Create a build using a custom method.
        """
        copr = get_copr()
        data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
        # pylint: disable-next=not-callable
        form = forms.BuildFormCustomFactory(copr.active_chroots)(data, meta={'csrf': False})

        def create_new_build(options):
            return BuildsLogic.create_new_from_custom(
                flask.g.user,
                copr,
                form.script.data,
                form.chroot.data,
                form.builddeps.data,
                form.resultdir.data,
                form.repos.data,
                **options,
            )

        return process_creating_new_build(copr, form, create_new_build)


@apiv3_builds_ns.route("/delete/<int:build_id>")
class DeleteBuild(Resource):
    @api_login_required
    @apiv3_builds_ns.doc(params=get_build_docs)
    @apiv3_builds_ns.marshal_with(build_model)
    def delete(self, build_id):
        """
        Delete a build
        Delete a build by its id.
        """
        build = ComplexLogic.get_build(build_id)
        build_dict = to_dict(build)
        BuildsLogic.delete_build(flask.g.user, build)
        db.session.commit()
        return build_dict


@apiv3_builds_ns.route("/delete/list")
class DeleteBuilds(Resource):
    @staticmethod
    def _common():
        build_ids = flask.request.json["builds"]
        BuildsLogic.delete_builds(flask.g.user, build_ids)
        db.session.commit()
        return {"builds": build_ids}

    @api_login_required
    @apiv3_builds_ns.expect(delete_builds_input_model)
    @apiv3_builds_ns.marshal_with(list_build_model)
    @deprecated_route_method_type(apiv3_builds_ns, "POST", "DELETE")
    def post(self):
        """
        Delete builds
        Delete builds specified by a list of IDs.
        """
        return self._common()

    @api_login_required
    @apiv3_builds_ns.expect(delete_builds_input_model)
    @apiv3_builds_ns.marshal_with(list_build_model)
    def delete(self):
        """
        Delete builds
        Delete builds specified by a list of IDs.
        """
        return self._common()


@apiv3_builds_ns.route("/check-before-build")
# this endoint is not meant to be used by the end user
@apiv3_builds_ns.hide
class CheckBeforeBuild(Resource):
    @api_login_required
    @apiv3_builds_ns.doc(
        responses={200: {"message": "It should be safe to submit a build like this"}}
    )
    def post(self):
        """
        Check before build
        Check if a build can be submitted (if the project exists, you have
        permissions, the chroot exists, etc). This is useful before trying to
        upload a large SRPM and failing to do so.
        """
        data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])

        # Raises an exception if project doesn't exist
        copr = get_copr()

        # Raises an exception if CoprDir doesn't exist
        if data.get("project_dirname"):
            CoprDirsLogic.get_or_validate(copr, data["project_dirname"])

        # Permissions check
        if not flask.g.user.can_build_in(copr):
            msg = ("User '{0}' is not allowed to build in '{1}'"
                   .format(flask.g.user.name, copr.full_name))
            raise AccessRestricted(msg)

        # Validation, i.e. check if chroot names are valid
        # pylint: disable=not-callable
        factory = forms.BuildFormCheckFactory(copr.active_chroots)
        form = factory(data, meta={'csrf': False})
        if not form.validate_on_submit():
            raise BadRequest("Bad request parameters: {0}".format(form.errors))

        return {"message": "It should be safe to submit a build like this"}
