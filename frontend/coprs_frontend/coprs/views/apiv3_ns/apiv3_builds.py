import flask
from . import get_copr
from werkzeug import secure_filename
from coprs import db, forms
from coprs.exceptions import ApiError, InsufficientRightsException, ActionInProgressException
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.builds_logic import BuildsLogic

# @TODO Don't import things from APIv1
from coprs.views.api_ns.api_general import validate_post_keys


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


@apiv3_ns.route("/build/cancel/<int:build_id>", methods=["POST"])
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    try:
        BuildsLogic.cancel_build(flask.g.user, build)
        db.session.commit()
    except InsufficientRightsException as e:
        raise ApiError("Invalid request: {}".format(e))
    return render_build(build)


@apiv3_ns.route("/build/create/url", methods=["POST"])
@api_login_required
def create_from_url():
    copr = get_copr()
    form = forms.BuildFormUrlFactory(copr.active_chroots)(csrf_enabled=False)

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
def create_from_upload():
    copr = get_copr()
    form = forms.BuildFormUploadFactory(copr.active_chroots)(csrf_enabled=False)

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
    form = forms.BuildFormScmFactory(copr.active_chroots)(csrf_enabled=False)

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
    form = forms.BuildFormPyPIFactory(copr.active_chroots)(csrf_enabled=False)

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
    form = forms.BuildFormRubyGemsFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_rubygems(
            flask.g.user,
            copr,
            form.gem_name.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


def process_creating_new_build(copr, form, create_new_build):
    if not form.validate_on_submit():
        raise ApiError("Invalid request: bad request parameters: {0}".format(form.errors))

    if not flask.g.user.can_build_in(copr):
        raise ApiError("Invalid request: user {} is not allowed to build in the copr: {}"
                       .format(flask.g.user.username, copr.full_name))

    # create a new build
    try:
        # From URLs it can be created multiple builds at once
        # so it can return a list
        build = create_new_build()
        db.session.commit()
    except (ActionInProgressException, InsufficientRightsException) as e:
        raise ApiError("Invalid request: {}".format(e))

    if type(build) == list:
        builds = [build] if type(build) != list else build
        return flask.jsonify(items=[to_dict(b) for b in builds], meta={})
    return flask.jsonify(to_dict(build))
