# coding: utf-8
import base64
import datetime
import functools
from logging import getLogger

from flask import url_for
import flask

from ..models import User, Copr, BuildChroot, Build
from ..logic.users_logic import UsersLogic
from ..logic.builds_logic import BuildsLogic
from ..logic.coprs_logic import CoprsLogic
from ..rest_api.schemas import BuildTaskSchema
from ..rest_api.util import mm_serialize_one, get_one_safe

from .exceptions import AuthFailed, ObjectNotFoundError
from .schemas import CoprChrootSchema, BuildSchema, ProjectSchema
from .util import mm_serialize_one

log = getLogger(__name__)


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
            "build_tasks": {"href": url_for(".buildtasklistr", build_id=build.id)}
        }
    }


def render_project(project, self_params=None):
    """
    :param Copr project:
    """
    if self_params is None:
        self_params = {}

    return {
        "project": mm_serialize_one(ProjectSchema, project),
        "_links": {
            "self": {"href": url_for(".projectr", project_id=project.id, **self_params)},
            "builds": {"href": url_for(".buildlistr", project_id=project.id)},
            "chroots": {"href": url_for(".projectchrootlistr", project_id=project.id)},
            "build_tasks": {"href":url_for(".buildtasklistr", project_id=project.id) }
        },
    }


def render_build_task(chroot):
    """
    :type chroot: BuildChroot
    """
    return {
        "build_task": mm_serialize_one(BuildTaskSchema, chroot),
        "_links": {
            "project": {"href": url_for(".projectr", project_id=chroot.build.copr_id)},
            "build": {"href": url_for(".buildr", build_id=chroot.build_id)},
            "self": {"href": url_for(".buildtaskr",
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
                (api_login, token) = userstring.decode("utf-8").split(":")
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


def get_project_safe(project_id):
    """
    :param int project_id:
    :rtype: Copr
    """
    return get_one_safe(
        CoprsLogic.get_by_id(project_id),
        msg="Project with id `{}` not found".format(project_id),
        data={"project_id": project_id}
    )


def get_build_safe(build_id):
    """
    :param int build_id:
    :rtype: Build
    """
    return get_one_safe(
        BuildsLogic.get(build_id),
        msg="Build with id `{}` not found".format(build_id),
        data={"build_id": build_id}
    )


def get_user_safe(username):
    """
    :param str username:
    :rtype: User
    """
    return get_one_safe(
        UsersLogic.get(username),
        msg="User `{}` doesn't have any project".format(username),
        data={"username": username}
    )
