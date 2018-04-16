import os
import flask
from . import query_params, get_copr
from coprs import db, models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.builds_logic import BuildsLogic
from coprs.helpers import fix_protocol_for_backend


def to_dict(copr):
    # @TODO review the fields
    copr_dict = {
        "name": copr.name,
        "owner": copr.owner_name,
        "full_name": copr.full_name,
        "additional_repos": copr.repos,
        "yum_repos": {},
        "description": copr.description,
        "instructions": copr.instructions,
        "last_modified": BuildsLogic.last_modified(copr),
        "auto_createrepo": copr.auto_createrepo,
        "persistent": copr.persistent,
        "unlisted_on_hp": copr.unlisted_on_hp,
        "auto_prune": copr.auto_prune,
        "use_bootstrap_container": copr.use_bootstrap_container,
    }

    # @TODO find a better place for yum_repos logic
    release_tmpl = "{chroot.os_release}-{chroot.os_version}-{chroot.arch}"
    build = models.Build.query.filter(models.Build.copr_id == copr.id).first()
    if build:
        for chroot in copr.active_chroots:
            release = release_tmpl.format(chroot=chroot)
            copr_dict["yum_repos"][release] = fix_protocol_for_backend(
                os.path.join(build.copr.repo_url, release + '/'))

    return copr_dict


@apiv3_ns.route("/project", methods=["GET"])
@query_params()
def get_project(ownername, projectname):
    copr = get_copr()
    return flask.jsonify(to_dict(copr))
