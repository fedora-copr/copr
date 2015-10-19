# coding: utf-8

import logging

log = logging.getLogger(__name__)

import flask
from flask import url_for, make_response
from flask_restful import Resource

from sqlalchemy.exc import IntegrityError

from ... import db
from ...logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic
from ...exceptions import InsufficientRightsException, MalformedArgumentException

from ..exceptions import AccessForbidden, MalformedRequest, \
    ObjectAlreadyExists, ServerError, ObjectNotFoundError
from ..common import rest_api_auth_required, render_copr_chroot, get_project_safe
from ..schemas import CoprChrootSchema, CoprChrootCreateSchema
from ..util import get_one_safe, mm_deserialize


class ProjectChrootListR(Resource):

    def get(self, project_id):
        project = get_project_safe(project_id)

        return {
            "chroots": [
                render_copr_chroot(chroot)
                for chroot in project.active_copr_chroots
            ],
            "_links": {
                "self": {"href": url_for(".projectchrootlistr", project_id=project_id)}
            }
        }

    @rest_api_auth_required
    def post(self, project_id):
        project = get_project_safe(project_id)

        chroot_data = mm_deserialize(CoprChrootCreateSchema(),
                                     flask.request.data.decode("utf-8"))

        req = chroot_data.data
        name = req.pop("name")

        try:
            mock_chroot = get_one_safe(MockChrootsLogic.get_from_name(name))
        except (MalformedArgumentException, ObjectNotFoundError) as err:
            raise MalformedRequest("Bad mock chroot name: {}. Error: {}".format(name, err))

        CoprChrootsLogic.create_chroot(flask.g.user, project, mock_chroot, **req)
        try:
            db.session.commit()
        except IntegrityError as err:
            # assuming conflict with existing chroot
            db.session.rollback()
            if get_one_safe(CoprChrootsLogic.get_by_name(project, name)) is not None:
                raise ObjectAlreadyExists("Copr {} already has chroot {} enabled"
                                          .format(project.full_name, name))

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".projectchrootr",
                                           project_id=project.id, name=name)
        return resp


class ProjectChrootR(Resource):

    @staticmethod
    def _get_chroot_safe(copr, name):
        try:
            chroot = get_one_safe(CoprChrootsLogic.get_by_name(copr, name))
        except MalformedArgumentException as err:
            raise MalformedRequest("Bad mock chroot name: {}".format(err))
        return chroot

    def get(self, project_id, name):
        project = get_project_safe(project_id)
        chroot = self._get_chroot_safe(project, name)

        return render_copr_chroot(chroot)

    @rest_api_auth_required
    def delete(self, project_id, name):
        project = get_project_safe(project_id)
        chroot = CoprChrootsLogic.get_by_name_safe(project, name)

        if chroot:
            try:
                CoprChrootsLogic.remove_copr_chroot(flask.g.user, chroot)
            except InsufficientRightsException as err:
                raise AccessForbidden("Failed to remove copr chroot: {}".format(err))

            db.session.commit()

        return "", 204

    @rest_api_auth_required
    def put(self, project_id, name):
        project = get_project_safe(project_id)
        chroot = self._get_chroot_safe(project, name)

        chroot_data = mm_deserialize(CoprChrootSchema(), flask.request.data.decode("utf-8"))
        try:
            updated_chroot = CoprChrootsLogic.update_chroot(
                user=flask.g.user,
                copr_chroot=chroot,
                **chroot_data.data
            )
        except InsufficientRightsException as err:
            raise AccessForbidden("Failed to update copr chroot: {}".format(err))

        db.session.commit()
        return render_copr_chroot(updated_chroot)
