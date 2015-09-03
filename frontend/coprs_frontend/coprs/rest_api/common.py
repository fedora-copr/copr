# coding: utf-8
import base64
import datetime
import functools
from logging import getLogger
from coprs.rest_api.schemas import BuildChrootSchema
from coprs.rest_api.util import mm_serialize_one

log = getLogger(__name__)

from flask import url_for
import flask

from ..logic.users_logic import UsersLogic
from .exceptions import AuthFailed
from .schemas import CoprChrootSchema, BuildSchema, ProjectSchema
from .util import mm_serialize_one


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


def render_build(build, self_params=None):
    if self_params is None:
        self_params = {}
    return {
        "build": BuildSchema().dump(build)[0],
        "_links": {
            "self": {"href": url_for(".buildr", build_id=build.id, **self_params)},
            "project": {"href": url_for(".projectr", project_id=build.copr_id)},
            "chroots": {"href": url_for(".buildchrootlistr", build_id=build.id)}
        }
    }


def render_project(copr, self_params=None):
    if self_params is None:
        self_params = {}

    return {
        "project": mm_serialize_one(ProjectSchema, copr),
        "_links": {
            "self": {"href": url_for(".projectr", project_id=copr.id, **self_params)},
            "builds": {"href": url_for(".buildlistr", project_id=copr.id)},
            "chroots": {"href": url_for(".projectchrootlistr", project_id=copr.id)}
        },
    }


def render_build_chroot(chroot):
    """
    :type chroot: models.BuildChroot
    """
    return {
        "chroot": mm_serialize_one(BuildChrootSchema, chroot),
        "_links": {
            "project": {"href": url_for(".projectr", project_id=chroot.build.copr_id)},
            "self": {"href": url_for(".buildchrootr",
                                     build_id=chroot.build.id,
                                     name=chroot.name)},
        }
    }



def rest_api_auth_required(f):
    # todo: move to common.py and test this
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        api_login = None
        try:
            if "Authorization" in flask.request.headers:
                base64string = flask.request.headers["Authorization"]
                base64string = base64string.split()[1].strip()
                userstring = base64.b64decode(base64string)
                (api_login, token) = userstring.split(":")
        except Exception:
            log.exception("Failed to get auth token from headers")
            api_login = token = None

        token_auth = False
        if token and api_login:
            user = UsersLogic.get_by_api_login(api_login).first()
            if (user and user.api_token == token and
                    user.api_token_expiration >= datetime.date.today()):

                token_auth = True
                flask.g.user = user
        if not token_auth:
            message = (
                "Login invalid/expired. "
                "Please visit https://copr.fedoraproject.org/api "
                "get or renew your API token.")

            raise AuthFailed(message)
        return f(*args, **kwargs)
    return decorated_function

