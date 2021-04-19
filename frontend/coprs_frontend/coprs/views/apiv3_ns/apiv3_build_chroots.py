import flask
from coprs.views.apiv3_ns import apiv3_ns
from coprs import models
from coprs.logic.builds_logic import BuildChrootsLogic
from coprs.logic.coprs_logic import CoprChrootsLogic
from coprs.logic.complex_logic import BuildConfigLogic, ComplexLogic
from . import query_params, pagination, Paginator, GET


def to_dict(build_chroot):
    return {
        "name": build_chroot.name,
        "started_on": build_chroot.started_on,
        "ended_on": build_chroot.ended_on,
        "result_url": build_chroot.result_dir_url,
        "state": build_chroot.state,
    }


def build_config(build_chroot):
    config = BuildConfigLogic.generate_build_config(build_chroot.build.copr, build_chroot.name)
    copr_chroot = CoprChrootsLogic.get_by_name_safe(build_chroot.build.copr, build_chroot.name)
    dict_data = {
        "repos": config.get("repos"),
        "additional_repos": BuildConfigLogic.generate_additional_repos(copr_chroot),
        "additional_packages": config.get("additional_packages"),
        "with_opts": config.get("with_opts"),
        "without_opts": config.get("without_opts"),
        "memory_limit": build_chroot.build.memory_reqs,
        "timeout": build_chroot.build.timeout,
        "enable_net": build_chroot.build.enable_net,
        "is_background": build_chroot.build.is_background,
    }
    dict_data.update(
        BuildConfigLogic.build_bootstrap_setup(config, build_chroot.build))
    return dict_data


@apiv3_ns.route("/build-chroot", methods=GET)
@apiv3_ns.route("/build-chroot/<int:build_id>/<chrootname>", methods=GET)  # deprecated
@query_params()
def get_build_chroot(build_id, chrootname):
    chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
    return flask.jsonify(to_dict(chroot))


@apiv3_ns.route("/build-chroot/list", methods=GET)
@apiv3_ns.route("/build-chroot/list/<int:build_id>", methods=GET)
@pagination()
@query_params()
def get_build_chroot_list(build_id, **kwargs):
    # For the python3-copr <= 1.105
    if kwargs.get("order") == "name":
        kwargs.pop("order")
    query = BuildChrootsLogic.filter_by_build_id(BuildChrootsLogic.get_multiply(), build_id)
    paginator = Paginator(query, models.BuildChroot, **kwargs)
    chroots = paginator.map(to_dict)
    return flask.jsonify(items=chroots, meta=paginator.meta)


@apiv3_ns.route("/build-chroot/build-config", methods=GET)
@apiv3_ns.route("/build-chroot/build-config/<int:build_id>/<chrootname>", methods=GET)  # deprecated
@query_params()
def get_build_chroot_config(build_id, chrootname):
    chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
    return flask.jsonify(build_config(chroot))


@apiv3_ns.route("/build-chroot/built-packages/", methods=GET)
@query_params()
def get_build_chroot_built_packages(build_id, chrootname):
    """
    Return built packages (NEVRA dicts) for a given build chroot
    """
    chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
    return flask.jsonify(chroot.results_dict)
