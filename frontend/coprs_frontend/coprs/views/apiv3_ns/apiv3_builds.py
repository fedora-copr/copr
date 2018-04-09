import flask
from coprs import db
from coprs.exceptions import ApiError, InsufficientRightsException
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


@apiv3_ns.route("/build/<int:build_id>/", methods=["GET"])
def get_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    return flask.jsonify(to_dict(build))


@apiv3_ns.route("/build/cancel/<int:build_id>", methods=["POST"])
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    try:
        BuildsLogic.cancel_build(flask.g.user, build)
        db.session.commit()
    except InsufficientRightsException as e:
        raise ApiError("Invalid request: {}".format(e))
    # @TODO eliminate the second request to database
    return get_build(build_id)
