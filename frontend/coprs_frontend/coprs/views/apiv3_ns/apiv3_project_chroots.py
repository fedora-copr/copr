import flask
from . import query_params, get_copr, file_upload
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import generate_build_config
from coprs.exceptions import ApiError
from coprs import db, models, forms
from coprs.logic.coprs_logic import CoprChrootsLogic


def to_dict(copr_chroot):
    return copr_chroot.to_dict()


@apiv3_ns.route("/project-chroot", methods=["GET"])
@query_params()
def get_project_chroot(ownername, projectname, chrootname):
    copr = get_copr()
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)
    return flask.jsonify(to_dict(chroot))


@apiv3_ns.route("/project-chroot/build-config", methods=["GET"])
@query_params()
def get_build_config(ownername, projectname, chrootname):
    copr = get_copr()
    config = generate_build_config(copr, chrootname)
    if not config:
        raise ApiError('Chroot not found.')
    return flask.jsonify(config)


@apiv3_ns.route("/project-chroot/edit", methods=["POST"])
@file_upload()
@query_params()
@api_login_required
def edit_project_chroot(ownername, projectname, chrootname):
    copr = get_copr()
    form = forms.ModifyChrootForm(csrf_enabled=False)
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)

    if not form.validate_on_submit():
        raise ApiError("Invalid request: {0}".format(form.errors))

    buildroot_pkgs = repos = comps_xml = comps_name = None
    if "buildroot_pkgs" in flask.request.form:
        buildroot_pkgs = form.buildroot_pkgs.data
    if "repos" in flask.request.form:
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
