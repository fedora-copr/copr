# All documentation is to be written on method-level because then it is
# recognized by flask-restx and rendered in Swagger
# pylint: disable=missing-class-docstring

import flask
from flask_restx import Namespace, Resource
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import (
    api,
    rename_fields_helper,
    query_to_parameters,
    deprecated_route_method_type,
)
from coprs.views.apiv3_ns.schema.schemas import (
    project_chroot_model,
    project_chroot_build_config_model,
    project_chroot_get_params,
)
from coprs.logic.complex_logic import ComplexLogic, BuildConfigLogic
from coprs.exceptions import ObjectNotFound, InvalidForm
from coprs import db, forms
from coprs.logic.coprs_logic import CoprChrootsLogic
from . import (
    get_copr,
    str_to_list,
    reset_to_defaults,
    file_upload,
)
from .json2form import get_form_compatible_data


apiv3_project_chroots_ns = \
    Namespace("project-chroot", description="Project chroots")
api.add_namespace(apiv3_project_chroots_ns)


def to_dict(project_chroot):
    return {
        "mock_chroot": project_chroot.mock_chroot.name,
        "projectname": project_chroot.copr.name,
        "ownername": project_chroot.copr.owner_name,
        "comps_name": project_chroot.comps_name,
        "additional_repos": project_chroot.repos_list,
        "additional_packages": project_chroot.buildroot_pkgs_list,
        "additional_modules": str_to_list(project_chroot.module_toggle, ", "),
        "with_opts": str_to_list(project_chroot.with_opts),
        "without_opts": str_to_list(project_chroot.without_opts),
        "delete_after_days": project_chroot.delete_after_days,
        "isolation": project_chroot.isolation,
    }


def to_build_config_dict(project_chroot):
    config = BuildConfigLogic.generate_build_config(project_chroot.copr, project_chroot.name)
    config_dict = {
        "chroot": project_chroot.name,
        "repos": config["repos"],
        "additional_repos": BuildConfigLogic.generate_additional_repos(project_chroot),
        "additional_packages": (project_chroot.buildroot_pkgs or "").split(),
        "additional_modules": str_to_list(project_chroot.module_toggle),
        "enable_net": project_chroot.copr.enable_net,
        "with_opts":  str_to_list(project_chroot.with_opts),
        "without_opts": str_to_list(project_chroot.without_opts),
        "isolation": project_chroot.isolation,
    }
    for option in ['bootstrap', 'bootstrap_image']:
        if option in config:
            config_dict[option] = config[option]
    return config_dict


def rename_fields(input_dict):
    return rename_fields_helper(input_dict, {
        "additional_repos": "repos",
        "additional_packages": "buildroot_pkgs",
        "additional_modules": "module_toggle",
    })


@apiv3_project_chroots_ns.route("/")
class ProjectChroot(Resource):
    @query_to_parameters
    @apiv3_project_chroots_ns.doc(params=project_chroot_get_params)
    @apiv3_project_chroots_ns.marshal_with(project_chroot_model)
    def get(self, ownername, projectname, chrootname):
        """
        Get a project chroot
        Get settings for a single project chroot.
        """
        copr = get_copr(ownername, projectname)
        chroot = ComplexLogic.get_copr_chroot(copr, chrootname)
        return to_dict(chroot)


@apiv3_project_chroots_ns.route("/build-config")
class BuildConfig(Resource):
    @query_to_parameters
    @apiv3_project_chroots_ns.doc(params=project_chroot_get_params)
    @apiv3_project_chroots_ns.marshal_with(project_chroot_build_config_model)
    def get(self, ownername, projectname, chrootname):
        """
        Get a build config
        Generate a build config based on a project chroot settings.
        """
        copr = get_copr(ownername, projectname)
        chroot = ComplexLogic.get_copr_chroot(copr, chrootname)
        if not chroot:
            raise ObjectNotFound('Chroot not found.')
        return to_build_config_dict(chroot)


@apiv3_project_chroots_ns.route("/edit/<ownername>/<projectname>/<chrootname>")
class EditChroot(Resource):
    def _common(self, ownername, projectname, chrootname):
        copr = get_copr(ownername, projectname)
        data = rename_fields(get_form_compatible_data(preserve=["additional_modules"]))
        form = forms.ModifyChrootForm(data, meta={'csrf': False})
        chroot = ComplexLogic.get_copr_chroot(copr, chrootname)

        if not form.validate_on_submit():
            raise InvalidForm(form)

        more_fields = ("See `copr-cli get-chroot {0}' for all the possible "
                       "attributes".format(chroot.full_name))
        reset_to_defaults(chroot, form, rename_fields, more_fields)

        buildroot_pkgs = repos = module_toggle = comps_xml = comps_name = with_opts = without_opts = None
        if "buildroot_pkgs" in data:
            buildroot_pkgs = form.buildroot_pkgs.data
        if "repos" in data:
            repos = form.repos.data
        if "module_toggle" in data:
            module_toggle = form.module_toggle.data
        if "with_opts" in data:
            with_opts = form.with_opts.data
        if "without_opts" in data:
            without_opts = form.without_opts.data
        if form.upload_comps.data:
            comps_xml = form.upload_comps.data.stream.read()
            comps_name = form.upload_comps.data.filename
        if form.delete_comps.data:
            CoprChrootsLogic.remove_comps(flask.g.user, chroot)
        CoprChrootsLogic.update_chroot(
            flask.g.user, chroot, buildroot_pkgs, repos, comps=comps_xml, comps_name=comps_name,
            with_opts=with_opts, without_opts=without_opts, module_toggle=module_toggle,
            bootstrap=form.bootstrap.data,
            bootstrap_image=form.bootstrap_image.data,
            isolation=form.isolation.data)
        db.session.commit()
        return to_dict(chroot)

    @deprecated_route_method_type(apiv3_project_chroots_ns, "POST", "PUT")
    @file_upload
    @api_login_required
    @apiv3_project_chroots_ns.doc(params=project_chroot_get_params)
    @apiv3_project_chroots_ns.marshal_with(project_chroot_model)
    def post(self, ownername, projectname, chrootname):
        """
        Edit a project chroot
        Edit settings for a single project chroot.
        """
        return self._common(ownername, projectname, chrootname)

    @file_upload
    @api_login_required
    @apiv3_project_chroots_ns.doc(params=project_chroot_get_params)
    @apiv3_project_chroots_ns.marshal_with(project_chroot_model)
    def put(self, ownername, projectname, chrootname):
        """
        Edit a project chroot
        Edit settings for a single project chroot.
        """
        return self._common(ownername, projectname, chrootname)
