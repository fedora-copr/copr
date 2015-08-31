# coding: utf-8
from flask import url_for
from coprs.rest_api.schemas import CoprChrootSchema, BuildSchema
from coprs.rest_api.util import mm_serialize_one


def render_copr_chroot(chroot):
    return {
        "chroot": mm_serialize_one(CoprChrootSchema, chroot),
        "_links": {
            "project": {"href": url_for(".projectr", project_id=chroot.copr.id)},
            "self": {"href": url_for(".projectchrootr",
                                     project_id=chroot.copr.id,
                                     name=chroot.name)},
        }
    }


def render_build(build):
    return {
        "build": BuildSchema().dump(build)[0],
        "_links": {
            "self": {"href": url_for(".buildr", build_id=build.id)},
            "project": {"href": url_for(".projectr", project_id=build.copr_id)},
            "chroots": {"href": url_for(".buildchrootlistr", build_id=build.id)}
        }
    }
