# coding: utf-8

import flask
from flask import url_for, make_response

# from flask_restful_swagger import swagger

from coprs import db, models
from coprs.exceptions import ActionInProgressException, InsufficientRightsException
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.users_logic import UsersLogic
from coprs.rest_api.exceptions import MalformedRequest, CannotProcessRequest, AccessForbidden
from coprs.rest_api.resources.project import rest_api_auth_required

from coprs.rest_api.schemas import BuildSchema, BuildCreateSchema, BuildCreateFromUrlSchema

from coprs.rest_api.util import get_one_safe, mm_deserialize

from flask_restful import Resource, reqparse


def render_build(build):
    return {
        "build": BuildSchema().dump(build)[0],
        "_links": {
            "self": {"href": url_for(".buildr", build_id=build.id)},
            "project": {"href": url_for(".projectr", project_id=build.copr_id)},
            "chroots": {"href": url_for(".buildchrootlistr", build_id=build.id)}
        }
    }


class BuildListR(Resource):

    def get(self):

        parser = reqparse.RequestParser()

        parser.add_argument('owner', type=str,)
        parser.add_argument('project_id', type=int)

        parser.add_argument('limit', type=int)
        parser.add_argument('offset', type=int)

        req_args = parser.parse_args()

        if req_args["project_id"] is not None:
            copr = get_one_safe(CoprsLogic.get_by_id(req_args["project_id"]))
            query = BuildsLogic.get_multiple_by_copr(copr)
        elif req_args["owner"] is not None:
            user = get_one_safe(UsersLogic.get(req_args["owner"]))
            query = BuildsLogic.get_multiple_by_owner(user)
        else:
            query = BuildsLogic.get_multiple()

        if "limit" in req_args:
            limit = req_args["limit"]
            if limit <= 0 or limit > 100:
                limit = 100
        else:
            limit = 100

        query = query.limit(limit)

        if "offset" in req_args:
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
        build_data = mm_deserialize(BuildCreateFromUrlSchema(), req.data)
        raise NotImplementedError()


    def handle_post_multipart(self, req):
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

        project = get_one_safe(CoprsLogic.get_by_id(project_id))
        """:type : models.Copr """

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
            raise CannotProcessRequest("Cannot create new build due to: {}"
                                       .format(err))
        except InsufficientRightsException as err:
            raise AccessForbidden("User {} cannon create build in project {}"
                                  .format(flask.g.user.username,
                                          project.full_name))

        return build.id

    @rest_api_auth_required
    def post(self):

        req = flask.request
        if "application/json" in req.content_type:
            build_id = self.handle_post_json(req)
        elif "multipart/form-data" in req.content_type :
            build_id = self.handle_post_multipart(req)
        else:
            raise MalformedRequest("Got unexpected content type: {}"
                                   .format(req.content_type))
        resp = make_response("", 201)
        resp.headers["Location"] = url_for(".buildr", build_id=build_id)

        return resp


class BuildR(Resource):

    def get(self, build_id):

        build = get_one_safe(BuildsLogic.get(build_id),
                             "Not found build with id: {}".format(build_id))

        return render_build(build)


# to get build details and cancel individual build chroots
# class BuildChrootR(Resource):
#     def get(self, owner, project, name):
#         copr = get_one_safe(CoprsLogic.get(flask.g.user, owner, project),
#                            "Copr {}/{} not found".format(owner, project))
#         chroot = get_one_safe(CoprChrootsLogic.get(copr, name))
#
#         return {
#             "chroot": chroot.to_dict(),
#             "links": {
#                 "self": bp_url_for(BuildChrootR.endpoint, owner=owner, project=project, name=name)
#             }
#         }

