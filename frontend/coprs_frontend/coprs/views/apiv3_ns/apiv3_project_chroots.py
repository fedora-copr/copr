import flask
from . import query_params, get_copr
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import generate_build_config
from coprs.exceptions import ApiError


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
