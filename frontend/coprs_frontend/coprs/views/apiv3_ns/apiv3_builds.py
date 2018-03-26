import flask
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic


@apiv3_ns.route("/build/<int:build_id>/", methods=["GET"])
def get_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)

    chroots = {}
    results_by_chroot = {}
    for chroot in build.build_chroots:
        chroots[chroot.name] = chroot.state
        results_by_chroot[chroot.name] = chroot.result_dir_url

    built_packages = None
    if build.built_packages:
        built_packages = build.built_packages.split("\n")

    # @TODO review the fields (missing ID, ...)
    # @TODO we dont't really want to define a dict here - maybe use build.to_dict() or something
    output = {
        "output": "ok",
        "status": build.state,
        "project": build.copr.name,
        "owner": build.copr.owner_name,
        "results": build.results,
        "built_pkgs": built_packages,
        "src_version": build.pkg_version,
        "chroots": chroots,
        "submitted_on": build.submitted_on,
        "started_on": build.min_started_on,
        "ended_on": build.max_ended_on,
        "src_pkg": build.pkgs,
        "submitted_by": build.user.name if build.user else None, # there is no user for webhook builds
        "results_by_chroot": results_by_chroot
    }
    return flask.jsonify(output)
