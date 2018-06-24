import flask
from werkzeug.datastructures import MultiDict
from . import get_copr, file_upload, query_params, pagination, Paginator, json2form
from .json2form import get_form_compatible_data, without_empty_fields
from werkzeug import secure_filename
from coprs import db, forms, models
from coprs.exceptions import ApiError, InsufficientRightsException, ActionInProgressException
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.builds_logic import BuildsLogic


def to_dict(build):
    chroots = {}
    results_by_chroot = {}
    for chroot in build.build_chroots:
        chroots[chroot.name] = chroot.state
        results_by_chroot[chroot.name] = chroot.result_dir_url

    built_packages = build.built_packages.split("\n") if build.built_packages else None

    # @TODO review the fields
    return {
        "id": build.id,
        "status": build.state,  # @TODO should this field be "status" or "state"?
        "project": build.copr.name,
        "owner": build.copr.owner_name,
        "results": build.copr.repo_url, # TODO: in new api return build results url
        "built_pkgs": built_packages,  # @TODO name of this property in model is "built_packages"
        "src_version": build.pkg_version,  # @TODO use "src_version" or "pkg_version"?
        "submitted_on": build.submitted_on,
        "started_on": build.min_started_on,
        "ended_on": build.max_ended_on,
        "src_pkg": build.pkgs,
        "submitted_by": build.user.name if build.user else None,  # there is no user for webhook builds
        "chroots": chroots,
        "results_by_chroot": results_by_chroot,
    }


def render_build(build):
    return flask.jsonify(to_dict(build))


@apiv3_ns.route("/build/<int:build_id>/", methods=["GET"])
def get_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    return render_build(build)


@apiv3_ns.route("/build/list/", methods=["GET"])
@pagination()
@query_params()
def get_build_list(ownername, projectname, packagename=None, status=None, **kwargs):
    copr = get_copr(ownername, projectname)
    query = BuildsLogic.get_multiple_by_copr(copr)
    if packagename:
        query = BuildsLogic.filter_by_package_name(query, packagename)

    # WORKAROUND
    # We can't filter builds by status directly in the database, because we
    # use a logic in Build.status property to determine a build status.
    # Therefore if we want to filter by `status`, we need to query all builds
    # and filter them in the application and then return the desired number.
    limit = kwargs["limit"]
    paginator_limit = None if status else kwargs["limit"]
    del kwargs["limit"]

    paginator = Paginator(query, models.Build, limit=paginator_limit, **kwargs)
    builds = paginator.map(to_dict)

    if status:
        builds = [b for b in builds if b["status"] == status][:limit]
        paginator.limit = limit

    return flask.jsonify(items=builds, meta=paginator.meta)


@apiv3_ns.route("/build/cancel/<int:build_id>", methods=["POST"])
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    try:
        BuildsLogic.cancel_build(flask.g.user, build)
        db.session.commit()
    except InsufficientRightsException as e:
        raise ApiError(e)
    return render_build(build)


@apiv3_ns.route("/build/create/url", methods=["POST"])
@api_login_required
def create_from_url():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.BuildFormUrlFactory(copr.active_chroots)(data, csrf_enabled=False)

    def create_new_build():
        # create separate build for each package
        pkgs = form.pkgs.data.split("\n")
        return [BuildsLogic.create_new_from_url(
            flask.g.user, copr,
            url=pkg,
            chroot_names=form.selected_chroots,
            background=form.background.data,
        ) for pkg in pkgs]
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/upload", methods=["POST"])
@api_login_required
@file_upload()
def create_from_upload():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.BuildFormUploadFactory(copr.active_chroots)(data, csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_upload(
            flask.g.user, copr,
            f_uploader=lambda path: form.pkgs.data.save(path),
            orig_filename=secure_filename(form.pkgs.data.filename),
            chroot_names=form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/scm", methods=["POST"])
@api_login_required
def create_from_scm():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.BuildFormScmFactory(copr.active_chroots)(data, csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_scm(
            flask.g.user,
            copr,
            scm_type=form.scm_type.data,
            clone_url=form.clone_url.data,
            committish=form.committish.data,
            subdirectory=form.subdirectory.data,
            spec=form.spec.data,
            srpm_build_method=form.srpm_build_method.data,
            chroot_names=form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/pypi", methods=["POST"])
@api_login_required
def create_from_pypi():
    copr = get_copr()
    data = MultiDict(json2form.without_empty_fields(json2form.get_input()))
    form = forms.BuildFormPyPIFactory(copr.active_chroots)(data, csrf_enabled=False)

    # TODO: automatically prepopulate all form fields with their defaults
    if not form.python_versions.data:
        form.python_versions.data = form.python_versions.default

    def create_new_build():
        return BuildsLogic.create_new_from_pypi(
            flask.g.user,
            copr,
            form.pypi_package_name.data,
            form.pypi_package_version.data,
            form.python_versions.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/rubygems", methods=["POST"])
@api_login_required
def create_from_rubygems():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.BuildFormRubyGemsFactory(copr.active_chroots)(data, csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_rubygems(
            flask.g.user,
            copr,
            form.gem_name.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@apiv3_ns.route("/build/create/custom", methods=["POST"])
@api_login_required
def create_from_custom():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.BuildFormCustomFactory(copr.active_chroots)(data, csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_custom(
            flask.g.user,
            copr,
            form.script.data,
            form.chroot.data,
            form.builddeps.data,
            form.resultdir.data,
            chroot_names=form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


def process_creating_new_build(copr, form, create_new_build):
    if not form.validate_on_submit():
        raise ApiError("Bad request parameters: {0}".format(form.errors))

    if not flask.g.user.can_build_in(copr):
        raise ApiError("User {} is not allowed to build in the copr: {}"
                       .format(flask.g.user.username, copr.full_name))

    # create a new build
    try:
        # From URLs it can be created multiple builds at once
        # so it can return a list
        build = create_new_build()
        db.session.commit()
    except (ActionInProgressException, InsufficientRightsException) as e:
        raise ApiError(e)

    if type(build) == list:
        builds = [build] if type(build) != list else build
        return flask.jsonify(items=[to_dict(b) for b in builds], meta={})
    return flask.jsonify(to_dict(build))


@apiv3_ns.route("/build/delete/<int:build_id>", methods=["POST"])
@api_login_required
def delete_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    build_dict = to_dict(build)
    try:
        BuildsLogic.delete_build(flask.g.user, build)
        db.session.commit()
    except (InsufficientRightsException, ActionInProgressException) as ex:
        raise ApiError(ex)
    return flask.jsonify(build_dict)
