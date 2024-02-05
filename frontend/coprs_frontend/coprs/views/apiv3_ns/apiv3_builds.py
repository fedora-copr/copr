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
from coprs.views.apiv3_ns import apiv3_ns, api, rename_fields_helper
from coprs.views.apiv3_ns.schema.schemas import build_model
from coprs.views.apiv3_ns.schema.docs import get_build_docs
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.coprs_logic import CoprDirsLogic

from . import (
    get_copr,
    file_upload,
    query_params,
    pagination,
    SubqueryPaginator,
    json2form,
    GET,
    POST,
    PUT,
    DELETE,
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


def render_build(build):
    return flask.jsonify(to_dict(build))


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

        # Workaround - `marshal_with` needs the input `build_id` to be present
        # in the returned dict. Don't worry, it won't get to the end user, it
        # will be stripped away.
        result["build_id"] = result["id"]
        return result


@apiv3_ns.route("/build/list/", methods=GET)
@pagination()
@query_params()
def get_build_list(ownername, projectname, packagename=None, status=None, **kwargs):
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

    return flask.jsonify(items=builds, meta=paginator.meta)


@apiv3_ns.route("/build/source-chroot/<int:build_id>/", methods=GET)
def get_source_chroot(build_id):
    build = ComplexLogic.get_build(build_id)
    return flask.jsonify(to_source_chroot(build))


@apiv3_ns.route("/build/source-build-config/<int:build_id>/", methods=GET)
def get_source_build_config(build_id):
    build = ComplexLogic.get_build(build_id)
    return flask.jsonify(to_source_build_config(build))


@apiv3_ns.route("/build/built-packages/<int:build_id>/", methods=GET)
def get_build_built_packages(build_id):
    """
    Return built packages (NEVRA dicts) for a given build
    """
    build = ComplexLogic.get_build(build_id)
    return flask.jsonify(build.results_dict)


@apiv3_ns.route("/build/cancel/<int:build_id>", methods=PUT)
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build(build_id)
    BuildsLogic.cancel_build(flask.g.user, build)
    db.session.commit()
    return render_build(build)


@apiv3_ns.route("/build/create/url", methods=POST)
@api_login_required
def create_from_url():
    copr = get_copr()
    data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
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


@apiv3_ns.route("/build/create/upload", methods=POST)
@api_login_required
@file_upload()
def create_from_upload():
    copr = get_copr()
    data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
    form = forms.BuildFormUploadFactory(copr.active_chroots)(data, meta={'csrf': False})

    def create_new_build(options):
        return BuildsLogic.create_new_from_upload(
            flask.g.user, copr,
            form.pkgs,
            orig_filename=secure_filename(form.pkgs.data.filename),
            **options,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/check-before-build", methods=POST)
@api_login_required
def check_before_build():
    """
    Check if a build can be submitted (if the project exists, you have
    permissions, the chroot exists, etc). This is useful before trying to
    upload a large SRPM and failing to do so.
    """
    data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])

    # Raises an exception if project doesn't exist
    copr = get_copr()

    # Raises an exception if CoprDir doesn't exist
    if data.get("project_dirname"):
        CoprDirsLogic.get_by_copr(copr, data["project_dirname"])

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


@apiv3_ns.route("/build/create/scm", methods=POST)
@api_login_required
def create_from_scm():
    copr = get_copr()
    data = rename_fields(get_form_compatible_data(preserve=["chroots", "exclude_chroots"]))
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

@apiv3_ns.route("/build/create/distgit", methods=POST)
@api_login_required
def create_from_distgit():
    """
    route for v3.proxies.create_from_distgit() call
    """
    copr = get_copr()
    data = rename_fields(get_form_compatible_data(preserve=["chroots", "exclude_chroots"]))
    # pylint: disable=not-callable
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

@apiv3_ns.route("/build/create/pypi", methods=POST)
@api_login_required
def create_from_pypi():
    copr = get_copr()
    data = MultiDict(json2form.without_empty_fields(json2form.get_input()))
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


@apiv3_ns.route("/build/create/rubygems", methods=POST)
@api_login_required
def create_from_rubygems():
    copr = get_copr()
    data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
    form = forms.BuildFormRubyGemsFactory(copr.active_chroots)(data, meta={'csrf': False})

    def create_new_build(options):
        return BuildsLogic.create_new_from_rubygems(
            flask.g.user,
            copr,
            form.gem_name.data,
            **options,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/custom", methods=POST)
@api_login_required
def create_from_custom():
    copr = get_copr()
    data = get_form_compatible_data(preserve=["chroots", "exclude_chroots"])
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
        return flask.jsonify(items=[to_dict(b) for b in builds], meta={})
    return flask.jsonify(to_dict(build))


@apiv3_ns.route("/build/delete/<int:build_id>", methods=DELETE)
@api_login_required
def delete_build(build_id):
    build = ComplexLogic.get_build(build_id)
    build_dict = to_dict(build)
    BuildsLogic.delete_build(flask.g.user, build)
    db.session.commit()
    return flask.jsonify(build_dict)


@apiv3_ns.route("/build/delete/list", methods=POST)
@api_login_required
def delete_builds():
    """
    Delete builds specified by a list of IDs.
    """
    build_ids = flask.request.json["builds"]
    BuildsLogic.delete_builds(flask.g.user, build_ids)
    db.session.commit()
    return flask.jsonify({"builds": build_ids})
