# coding: utf-8
import json
from flask import Response, url_for, Blueprint, make_response
from flask_restful import Resource, Api

from coprs.exceptions import InsufficientRightsException

from coprs.rest_api.exceptions import ApiError
from coprs.rest_api.resources.build import BuildListR, BuildR
from coprs.rest_api.resources.build_task import BuildTaskListR, BuildTaskR
from coprs.rest_api.resources.mock_chroot import MockChrootListR, MockChrootR
from coprs.rest_api.resources.project import ProjectListR, ProjectR
from coprs.rest_api.resources.project_chroot import ProjectChrootListR, ProjectChrootR

URL_PREFIX = "/api_2"


class RootR(Resource):
    @classmethod
    def get(cls):
        return {
            "_links": {
                "self": {"href": url_for(".rootr")},
                "projects": {
                    "href": url_for(".projectlistr"),
                    "query_params": [
                        {
                            "name": u"owner",
                            "type": u"string",
                            "description": u"Select only project owned by the user"
                        }
                    ]
                },
                "mock_chroots": {"href": url_for(".mockchrootlistr")},
                "builds": {"href": url_for(".buildlistr")},
                "build_tasks": {"href": url_for(".buildtasklistr")},
            }
        }


class MyApi(Api):
    # flask-restfull error handling quite buggy right now
    def error_router(self, original_handler, e):
        return original_handler(e)
#     # def handle_error(self, e):
#     #
#     #     if isinstance(e, sqlalchemy.orm.exc.NoResultFound):
#     #         return self.make_response(str(e), 404)
#     #
#     #
#     #     super(MyApi, self).handle_error(e)


# def register_api(app, db):


rest_api_bp = Blueprint("rest_api_bp", __name__)
api = MyApi(rest_api_bp, catch_all_404s=True)

api.add_resource(RootR, "/")
api.add_resource(ProjectListR, "/projects")
api.add_resource(ProjectR, "/projects/<int:project_id>")

api.add_resource(MockChrootListR, "/mock_chroots")
api.add_resource(MockChrootR, "/mock_chroots/<name>")

api.add_resource(BuildListR, "/builds")
api.add_resource(BuildR, "/builds/<int:build_id>")

api.add_resource(ProjectChrootListR, "/projects/<int:project_id>/chroots")
api.add_resource(ProjectChrootR, "/projects/<int:project_id>/chroots/<name>")


api.add_resource(BuildTaskListR, "/build_tasks")
# todo: add redirect from /build_tasks/<int:build_id> -> /build_tasks?build_id=<build_id>
api.add_resource(BuildTaskR, "/build_tasks/<int:build_id>/<name>")


def register_api_error_handler(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        """
        :param ApiError error:
        """

        content = {
            "message": error.msg,
        }
        if error.data:
            content["data"] = error.data

        response = make_response(json.dumps(content), error.code)
        response.headers["Content-Type"] = "application/json"
        return response
