# coding: utf-8

import flask
from flask import url_for, make_response
from flask_restful import Resource, reqparse

from ... import db
from ...exceptions import ActionInProgressException, InsufficientRightsException, RequestCannotBeExecuted
from ...helpers import StatusEnum
from ...logic.builds_logic import BuildsLogic
from ..common import get_project_safe
from ..exceptions import MalformedRequest, CannotProcessRequest, AccessForbidden
from ..common import render_build, rest_api_auth_required, render_build_task, get_build_safe, get_user_safe
from ..schemas import BuildSchema, BuildCreateSchema, BuildCreateFromUrlSchema
from ..util import mm_deserialize, get_request_parser, arg_bool


class BuildListR(Resource):

    def get(self):

        parser = get_request_parser()

        parser.add_argument('owner', type=str,)
        parser.add_argument('project_id', type=int)
        parser.add_argument('group', type=str)

        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        parser.add_argument('is_finished', type=arg_bool)
        # parser.add_argument('package', type=str)

        req_args = parser.parse_args()

        if req_args["project_id"] is not None:
            project = get_project_safe(req_args["project_id"])
            query = BuildsLogic.get_multiple_by_copr(project)
        elif req_args["owner"] is not None:
            user = get_user_safe(req_args["owner"])
            query = BuildsLogic.get_multiple_by_owner(user)
        else:
            query = BuildsLogic.get_multiple()

        if req_args["group"]:
            query = BuildsLogic.filter_by_group_name(query, req_args["group"])

        if req_args["is_finished"] is not None:
            is_finished = req_args["is_finished"]
            query = BuildsLogic.filter_is_finished(query, is_finished)

        if req_args["limit"] is not None:
            limit = req_args["limit"]
            if limit <= 0 or limit > 100:
                limit = 100
        else:
            limit = 100

        query = query.limit(limit)

        if req_args["offset"] is not None:
            query = query.offset(req_args["offset"])

        builds = query.all()

        self_params = dict(req_args)
        self_params["limit"] = limit
        return {
            "builds": [
                render_build(build) for build in builds
            ],
            "_links": {
                "self": {"href": url_for(".buildlistr", **self_params)},
            },
        }

    def handle_post_json(self, req):
        """
        :return: if of the created build or raise Exception
        """
        build_params = mm_deserialize(BuildCreateFromUrlSchema(), req.data.decode("utf-8")).data
        project = get_project_safe(build_params["project_id"])

        chroot_names = build_params.pop("chroots")
        srpm_url = build_params.pop("srpm_url")
        try:
            build = BuildsLogic.create_new_from_url(
                flask.g.user, project,
                srpm_url=srpm_url,
                chroot_names=chroot_names,
                **build_params
            )
            db.session.commit()
        except ActionInProgressException as err:
            db.session.rollback()
            raise CannotProcessRequest("Cannot create new build due to: {}"
                                       .format(err))
        except InsufficientRightsException as err:
            db.session.rollback()
            raise AccessForbidden("User {} cannon create build in project {}: {}"
                                  .format(flask.g.user.username,
                                          project.full_name, err))
        return build.id

    @staticmethod
    def handle_post_multipart(req):
        """
        :return: if of the created build or raise Exception
        """
        try:
            metadata = req.form["metadata"]
        except KeyError:
            raise MalformedRequest("Missing build metadata in the request")

        if "srpm" not in req.files:
            raise MalformedRequest("Missing srpm file in the request")
        srpm_handle = req.files["srpm"]

        build_params = mm_deserialize(BuildCreateSchema(), metadata).data
        project_id = build_params["project_id"]

        project = get_project_safe(project_id)

        chroot_names = build_params.pop("chroots")
        try:
            build = BuildsLogic.create_new_from_upload(
                flask.g.user, project,
                f_uploader=lambda path: srpm_handle.save(path),
                orig_filename=srpm_handle.filename,
                chroot_names=chroot_names,
                **build_params
            )
            db.session.commit()
        except ActionInProgressException as err:
            db.session.rollback()
            raise CannotProcessRequest("Cannot create new build due to: {}"
                                       .format(err))
        except InsufficientRightsException as err:
            db.session.rollback()
            raise AccessForbidden("User {} cannon create build in project {}: {}"
                                  .format(flask.g.user.username,
                                          project.full_name, err))

        return build.id

    @rest_api_auth_required
    def post(self):

        req = flask.request
        if "application/json" in req.content_type:
            build_id = self.handle_post_json(req)
        elif "multipart/form-data" in req.content_type:
            build_id = self.handle_post_multipart(req)
        else:
            raise MalformedRequest("Got unexpected content type: {}"
                                   .format(req.content_type))
        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".buildr", build_id=build_id)

        return resp


class BuildR(Resource):

    def get(self, build_id):
        parser = get_request_parser()
        parser.add_argument('show_build_tasks', type=arg_bool, default=False)
        req_args = parser.parse_args()

        build = get_build_safe(build_id)

        self_params = {}
        if req_args["show_build_tasks"]:
            self_params["show_build_tasks"] = req_args["show_build_tasks"]

        result = render_build(build, self_params)
        if req_args["show_build_tasks"]:
            result["build_tasks"] = [
                render_build_task(chroot)
                for chroot in build.build_chroots
            ]

        return result

    @rest_api_auth_required
    def delete(self, build_id):
        build = get_build_safe(build_id)
        try:
            BuildsLogic.delete_build(flask.g.user, build)
            db.session.commit()
        except ActionInProgressException as err:
            db.session.rollback()
            raise CannotProcessRequest("Cannot delete build due to: {}"
                                       .format(err))
        except InsufficientRightsException as err:
            raise AccessForbidden("Failed to delete build: {}".format(err))

        return "", 204

    @rest_api_auth_required
    def put(self, build_id):
        build = get_build_safe(build_id)
        build_dict = mm_deserialize(BuildSchema(), flask.request.data.decode("utf-8")).data
        try:
            if not build.canceled and build_dict["state"] == "canceled":
                BuildsLogic.cancel_build(flask.g.user, build)
                db.session.commit()
        except (RequestCannotBeExecuted, ActionInProgressException) as err:
            db.session.rollback()
            raise CannotProcessRequest("Cannot update build due to: {}"
                                       .format(err))
        except InsufficientRightsException as err:
            raise AccessForbidden("Failed to update build: {}".format(err))

        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".buildr", build_id=build_id)
        return resp
