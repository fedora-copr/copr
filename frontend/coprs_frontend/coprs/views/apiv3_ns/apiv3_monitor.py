"""
/api_3/monitor routes
"""

import flask

from coprs.exceptions import BadRequest
from coprs.logic.builds_logic import BuildsMonitorLogic
from coprs.logic.coprs_logic import CoprDirsLogic
from coprs.views.apiv3_ns import (
    apiv3_ns,
    GET,
    get_copr,
    query_params,
    streamed_json_array_response,
)

from coprs.measure import checkpoint

def monitor_generator(copr_dir, additional_fields):
    """
    Continuosly fill-up the package_monitor() buffer.
    """
    anti_garbage_collector = set([copr_dir])
    packages = BuildsMonitorLogic.package_build_chroots(copr_dir)
    first = True
    for package in packages:
        if first is True:
            checkpoint("First package queried")
            first = False
        chroots = {}
        for bch in package["chroots"]:
            chroot = chroots[bch.name] = {}
            for attr in ["state", "status", "build_id"]:
                chroot[attr] = getattr(bch, attr)
            if "url_build_log" in additional_fields:
                chroot["url_build_log"] = bch.rpm_live_log_url
            if "url_backend_log" in additional_fields:
                chroot["url_backend_log"] = bch.rpm_backend_log_url
            # anti-gc, this is a very small set of items
            anti_garbage_collector.add(bch.mock_chroot)
            anti_garbage_collector.add(bch.build.copr_dir)
            chroot["pkg_version"] = bch.build.pkg_version
        yield {
            "name": package["name"],
            "chroots": chroots,
        }
    checkpoint("Last package queried")


@apiv3_ns.route("/monitor", methods=GET)
@query_params()
def package_monitor(ownername, projectname, project_dirname=None):
    """
    For list of the project packages return list of JSON dictionaries informing
    about status of the last chroot builds (status, build log, etc.).
    """
    checkpoint("API3 monitor start")

    additional_fields = flask.request.args.getlist("additional_fields[]")

    copr = get_copr(ownername, projectname)

    valid_additional_fields = [
        "url_build_log",
        "url_backend_log",
        "url_build",
    ]

    if additional_fields:
        additional_fields = set(additional_fields)
        bad_fields = []
        for field in sorted(additional_fields):
            if field not in valid_additional_fields:
                bad_fields += [field]
        if bad_fields:
            raise BadRequest(
                "Wrong additional_fields argument(s): " +
                ", ".join(bad_fields)
            )
    else:
        additional_fields = set()

    if project_dirname:
        copr_dir = CoprDirsLogic.get_by_copr(copr, project_dirname)
    else:
        copr_dir = copr.main_dir

    # Preload those to avoid the error sqlalchemy.orm.exc.DetachedInstanceError
    # http://sqlalche.me/e/13/bhk3
    _ = copr_dir.copr.active_chroots
    _ = copr_dir.copr.group

    try:
        return streamed_json_array_response(
            monitor_generator(copr_dir, additional_fields),
            "Project monitor request successful",
            "packages",
        )
    finally:
        checkpoint("Streaming prepared")
