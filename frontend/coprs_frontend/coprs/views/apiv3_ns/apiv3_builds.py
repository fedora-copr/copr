import os
import flask
from sqlalchemy.orm import joinedload

from werkzeug.datastructures import MultiDict
from werkzeug.utils import secure_filename

from copr_common.enums import StatusEnum
from coprs import db, forms, models
from coprs.exceptions import (BadRequest, AccessRestricted)
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.builds_logic import BuildsLogic

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


def rename_fields(input):
    replace = {
        "source_build_method": "srpm_build_method",
    }
    output = input.copy()
    for from_name, to_name in replace.items():
        if from_name not in output:
            continue
        output[to_name] = output.pop(from_name)
    return output


def render_build(build):
    return flask.jsonify(to_dict(build))


@apiv3_ns.route("/build/<int:build_id>/", methods=GET)
@apiv3_ns.route("/build/<int:build_id>", methods=GET)
def get_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    return render_build(build)


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
    build = ComplexLogic.get_build_safe(build_id)
    return flask.jsonify(to_source_chroot(build))


@apiv3_ns.route("/build/source-build-config/<int:build_id>/", methods=GET)
def get_source_build_config(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    return flask.jsonify(to_source_build_config(build))


@apiv3_ns.route("/build/built-packages/<int:build_id>/", methods=GET)
def get_build_built_packages(build_id):
    """
    Return built packages (NEVRA dicts) for a given build
    """
    build = ComplexLogic.get_build_safe(build_id)
    return flask.jsonify(build.results_dict)


@apiv3_ns.route("/build/cancel/<int:build_id>", methods=PUT)
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
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
    build = ComplexLogic.get_build_safe(build_id)
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
