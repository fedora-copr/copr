# pylint: disable=missing-class-docstring

from http import HTTPStatus

from flask_restx import Namespace, Resource

from coprs.views.apiv3_ns import api, query_to_parameters
from coprs import models
from coprs.logic.builds_logic import BuildChrootsLogic
from coprs.logic.coprs_logic import CoprChrootsLogic
from coprs.logic.complex_logic import BuildConfigLogic, ComplexLogic
from coprs.views.apiv3_ns.schema.schemas import (
    build_chroot_model,
    build_chroot_params,
    build_id_params,
    pagination_params,
    pagination_build_chroot_model,
    build_chroot_config_model,
    nevra_packages_model,
)
from coprs.views.apiv3_ns import pagination
from . import Paginator


apiv3_bchroots_ns = Namespace("build-chroot", description="Build Chroots")
api.add_namespace(apiv3_bchroots_ns)


def to_dict(build_chroot):
    return {
        "name": build_chroot.name,
        "started_on": build_chroot.started_on,
        "ended_on": build_chroot.ended_on,
        "result_url": build_chroot.result_dir_url,
        "state": build_chroot.state,
    }


def build_config(build_chroot):
    config = BuildConfigLogic.generate_build_config(
        build_chroot.build.copr_dir, build_chroot.name)
    copr_chroot = CoprChrootsLogic.get_by_name_or_none(build_chroot.build.copr, build_chroot.name)
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


@apiv3_bchroots_ns.route("/")
@apiv3_bchroots_ns.route(
    "/<int:build_id>/<chrootname>",
    doc={"deprecated": True, "description": "Use query parameters instead"},
)
class BuildChroot(Resource):
    @query_to_parameters
    @apiv3_bchroots_ns.doc(params=build_chroot_params)
    @apiv3_bchroots_ns.marshal_with(build_chroot_model)
    @apiv3_bchroots_ns.response(HTTPStatus.OK.value, "OK, Build chroot data follows...")
    @apiv3_bchroots_ns.response(
        HTTPStatus.NOT_FOUND.value, "No such Build chroot exist"
    )
    def get(self, build_id, chrootname):
        """
        Get build chroot
        Get information about specific build chroot by build id and mock chroot name.
        """
        chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
        return to_dict(chroot)


@apiv3_bchroots_ns.route("/list")
@apiv3_bchroots_ns.route(
    "/list/<int:build_id>",
    doc={"deprecated": True, "description": "Use query parameters instead"},
)
class BuildChrootList(Resource):
    @pagination
    @query_to_parameters
    @apiv3_bchroots_ns.doc(params=build_id_params | pagination_params)
    @apiv3_bchroots_ns.marshal_list_with(pagination_build_chroot_model)
    @apiv3_bchroots_ns.response(
        HTTPStatus.PARTIAL_CONTENT.value, HTTPStatus.PARTIAL_CONTENT.description
    )
    def get(self, build_id, **kwargs):
        """
        List Build chroots
        List build chroots by build id and pagination query.
        """
        # For the python3-copr <= 1.105
        if kwargs.get("order") == "name":
            kwargs.pop("order")
        query = BuildChrootsLogic.filter_by_build_id(BuildChrootsLogic.get_multiply(), build_id)
        paginator = Paginator(query, models.BuildChroot, **kwargs)
        chroots = paginator.map(to_dict)
        return {"items": chroots, "meta": paginator.meta}


@apiv3_bchroots_ns.route("/build-config")
@apiv3_bchroots_ns.route(
    "/build-config/<int:build_id>/<chrootname>",
    doc={"deprecated": True, "description": "Use query parameters instead"},
)
class BuildChrootConfig(Resource):
    @query_to_parameters
    @apiv3_bchroots_ns.doc(params=build_chroot_params)
    @apiv3_bchroots_ns.marshal_with(build_chroot_config_model, skip_none=True)
    @apiv3_bchroots_ns.response(HTTPStatus.OK.value, "OK, Build chroot config follows...")
    @apiv3_bchroots_ns.response(
        HTTPStatus.NOT_FOUND.value, "No such Build chroot exist"
    )
    def get(self, build_id, chrootname):
        """
        Get Build chroot config
        Get Build chroot by build id and its mock chroot name.
        """
        chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
        return build_config(chroot)


@apiv3_bchroots_ns.route("/built-packages")
class BuildChrootPackages(Resource):
    @query_to_parameters
    @apiv3_bchroots_ns.doc(params=build_chroot_params)
    @apiv3_bchroots_ns.marshal_with(nevra_packages_model)
    @apiv3_bchroots_ns.response(
        HTTPStatus.OK.value, "OK, dict containing all built packages in this chroot follows..."
    )
    @apiv3_bchroots_ns.response(
        HTTPStatus.NOT_FOUND.value, "No such Build chroot exist"
    )
    def get(self, build_id, chrootname):
        """
        Get built packages
        Get built packages (NEVRA dicts) for a given mock chroot name.
        """
        chroot = ComplexLogic.get_build_chroot(build_id, chrootname)
        return chroot.results_dict
