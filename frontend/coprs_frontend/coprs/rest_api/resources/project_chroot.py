# coding: utf-8

import json
import logging
log = logging.getLogger(__name__)

import flask
from flask import url_for, make_response
from flask_restful import Resource, reqparse

from marshmallow import Schema, fields, pprint, ValidationError
from sqlalchemy.exc import IntegrityError
from coprs.exceptions import InsufficientRightsException, MalformedArgumentException
from coprs.rest_api.exceptions import AccessForbidden, ObjectNotFoundError, MalformedRequest, ObjectAlreadyExists, \
    ServerError
from coprs.rest_api.resources.project import rest_api_auth_required
from coprs.rest_api.schemas import MockChrootSchema, CoprChrootSchema, CoprChrootCreateSchema

from coprs.views.misc import api_login_required
from coprs.logic.coprs_logic import MockChrootsLogic, CoprChrootsLogic, CoprsLogic

from ..util import get_one_safe, json_loads_safe, mm_deserialize, mm_serialize_one
from ... import db


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


class ProjectChrootListR(Resource):

    def get(self, project_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        return {
            "chroots": [
                render_copr_chroot(chroot)
                for chroot in copr.copr_chroots
            ],
            "_links": {
                "self": {"href": url_for(".projectchrootlistr", project_id=project_id)}
            }
        }

    @rest_api_auth_required
    def post(self, project_id):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))

        chroot_data = mm_deserialize(CoprChrootCreateSchema(),
                                     flask.request.data)

        req = chroot_data.data
        name = req.pop("name")

        try:
            mock_chroot = get_one_safe(MockChrootsLogic.get_from_name(name))
        except MalformedArgumentException as err:
            raise MalformedRequest("Bad mock chroot name: {}".format(err))

        if mock_chroot is None:
            raise MalformedRequest("Mock chroot `{}` doesn't exists"
                                   .format(name))
        CoprChrootsLogic.create_chroot(flask.g.user, copr, mock_chroot, **req)
        try:
            db.session.commit()
        except IntegrityError as err:
            # assuming conflict with existing chroot
            db.session.rollback()
            if get_one_safe(CoprChrootsLogic.get_by_name(copr, name)) is not None:
                raise ObjectAlreadyExists("Copr {} already has chroot {} enabled"
                                          .format(copr.full_name, name))
            else:
                raise ServerError("Unexpected error, contact site administrator: {}"
                                  .format(err))

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".projectchrootr",
                                           project_id=copr.id, name=name)
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
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = self._get_chroot_safe(copr, name)

        return render_copr_chroot(chroot)

    @rest_api_auth_required
    def delete(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = CoprChrootsLogic.get_by_name_safe(copr, name)

        if chroot:
            try:
                CoprChrootsLogic.remove_copr_chroot(flask.g.user, chroot)
            except InsufficientRightsException as err:
                raise AccessForbidden("Failed to remove copr chroot: {}".format(err))

            db.session.commit()

        return "", 204

    @rest_api_auth_required
    def put(self, project_id, name):
        copr = get_one_safe(CoprsLogic.get_by_id(int(project_id)))
        chroot = self._get_chroot_safe(copr, name)

        chroot_data = mm_deserialize(CoprChrootSchema(), flask.request.data)
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
