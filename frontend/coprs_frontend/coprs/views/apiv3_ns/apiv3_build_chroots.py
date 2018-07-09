import flask
from . import query_params, pagination, Paginator, GET
from coprs.views.apiv3_ns import apiv3_ns
from coprs.helpers import generate_build_config, generate_additional_repos
from coprs import db, models, forms
from coprs.logic.builds_logic import BuildChrootsLogic, BuildsLogic
from coprs.logic.coprs_logic import CoprChrootsLogic


def to_dict(build_chroot):
    return {
        "name": build_chroot.name,
        "started_on": build_chroot.started_on,
        "ended_on": build_chroot.ended_on,
        "result_url": build_chroot.result_dir_url,
    }


def build_config(build_chroot):
    config = generate_build_config(build_chroot.build.copr, build_chroot.name)
    copr_chroot = CoprChrootsLogic.get_by_name_safe(build_chroot.build.copr, build_chroot.name)
    return {
        "additional_repos": generate_additional_repos(copr_chroot),
        "additional_packages": config.get("additional_packages"),
        "use_bootstrap_container": config.get("use_bootstrap_container"),
        "with_opts": config.get("with_opts"),
        "without_opts": config.get("without_opts"),
        "memory_limit": build_chroot.build.memory_reqs,
        "timeout": build_chroot.build.timeout,
        "enable_net": build_chroot.build.enable_net,
        "is_background": build_chroot.build.is_background,
    }


@apiv3_ns.route("/build-chroot/<int:build_id>/<chrootname>", methods=GET)
def get_build_chroot(build_id, chrootname):
    chroot = BuildChrootsLogic.get_by_build_id_and_name(build_id, chrootname).one()
    return flask.jsonify(to_dict(chroot))


@apiv3_ns.route("/build-chroot/list/<int:build_id>", methods=GET)
@pagination()
@query_params()
def get_build_chroot_list(build_id, **kwargs):
    query = BuildChrootsLogic.filter_by_build_id(BuildChrootsLogic.get_multiply(), build_id)
    paginator = Paginator(query, models.BuildChroot, **kwargs)
    chroots = paginator.map(to_dict)
    return flask.jsonify(items=chroots, meta=paginator.meta)


@apiv3_ns.route("/build-chroot/build-config/<int:build_id>/<chrootname>", methods=GET)
def get_build_chroot_config(build_id, chrootname):
    chroot = BuildChrootsLogic.get_by_build_id_and_name(build_id, chrootname).one()
    return flask.jsonify(build_config(chroot))
