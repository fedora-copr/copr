import flask
from . import query_params, get_copr, file_upload, GET, POST, PUT, DELETE
from .json2form import get_form_compatible_data
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import generate_build_config
from coprs.exceptions import ApiError
from coprs import db, models, forms
from coprs.logic.coprs_logic import CoprChrootsLogic


def to_dict(project_chroot):
    return {
        "mock_chroot": project_chroot.mock_chroot.name,
        "projectname": project_chroot.copr.name,
        "ownername": project_chroot.copr.owner_name,
        "comps_name": project_chroot.comps_name,
        "additional_repos": project_chroot.repos_list,
        "additional_packages": project_chroot.buildroot_pkgs_list,
        "with_opts": str_to_list(project_chroot.with_opts),
        "without_opts": str_to_list(project_chroot.without_opts),
    }


def str_to_list(value):
    return (value or "").split()


@apiv3_ns.route("/project-chroot", methods=GET)
@query_params()
def get_project_chroot(ownername, projectname, chrootname):
    copr = get_copr(ownername, projectname)
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)
    return flask.jsonify(to_dict(chroot))


@apiv3_ns.route("/project-chroot/build-config", methods=GET)
@query_params()
def get_build_config(ownername, projectname, chrootname):
    copr = get_copr(ownername, projectname)
    config = generate_build_config(copr, chrootname)
    if not config:
        raise ApiError('Chroot not found.')
    return flask.jsonify(config)


@apiv3_ns.route("/project-chroot/edit/<ownername>/<projectname>/<chrootname>", methods=PUT)
@file_upload()
@api_login_required
def edit_project_chroot(ownername, projectname, chrootname):
    copr = get_copr(ownername, projectname)
    data = get_form_compatible_data()
    form = forms.ModifyChrootForm(data, csrf_enabled=False)
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)

    if not form.validate_on_submit():
        raise ApiError(form.errors)

    buildroot_pkgs = repos = comps_xml = comps_name = None
    if "buildroot_pkgs" in data:
        buildroot_pkgs = form.buildroot_pkgs.data
    if "repos" in data:
        repos = form.repos.data
    if form.upload_comps.has_file():
        comps_xml = form.upload_comps.data.stream.read()
        comps_name = form.upload_comps.data.filename
    if form.delete_comps.data:
        CoprChrootsLogic.remove_comps(flask.g.user, chroot)
    CoprChrootsLogic.update_chroot(
        flask.g.user, chroot, buildroot_pkgs, repos, comps=comps_xml, comps_name=comps_name)
    db.session.commit()
    return flask.jsonify(to_dict(chroot))
