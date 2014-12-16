# coding: utf-8
from flask import Response, url_for, Blueprint

from flask_restful import Resource, Api
from flask_restful_swagger import swagger

from coprs.rest_api.exceptions import ApiError
from coprs.rest_api.resources.build import BuildListR, BuildR
from coprs.rest_api.resources.chroot import ChrootListR, ChrootR
from coprs.rest_api.resources.copr import CoprListR, CoprR
from coprs.rest_api.util import bp_url_for


URL_PREFIX = "/api_2.0"


class RootR(Resource):
    @swagger.operation(
        notes='List main API endpoints',
        nickname='get',
    )
    def get(self):
        return {
            "links": {
                "self": bp_url_for(RootR.endpoint),
                "coprs": bp_url_for(CoprListR.endpoint),
                "chroots": bp_url_for(ChrootListR.endpoint),
                "builds": bp_url_for(BuildListR.endpoint),
            }
        }


class MyApi(Api):
    # flask-restfull error handling quite buggy right now
    def error_router(self, original_handler, e):
        return original_handler(e)
    # def handle_error(self, e):
    #
    #     if isinstance(e, sqlalchemy.orm.exc.NoResultFound):
    #         return self.make_response(str(e), 404)
    #
    #
    #     super(MyApi, self).handle_error(e)


# def register_api(app, db):


rest_api_bp = Blueprint("rest_api_bp",
               __name__,
               # app.import_name
)

api = MyApi(
# api = Api(
    #     app,
    rest_api_bp,
    # prefix=URL_PREFIX,
    catch_all_404s=True,

)

###################################
# todo: maybe add later
# Wrap the Api with swagger.docs. It is a thin wrapper around the Api class that adds some swagger smarts
# api = swagger.docs(
#     api,
#     # apiVersion='0.1',
#     # basePath=URL_PREFIX,
#     # resourcePath=URL_PREFIX,
#     # api_spec_url='{}/spec'.format(URL_PREFIX)
#     # api_spec_url='/spec',
#     # api_spec_url='{}/spec'.format(URL_PREFIX)
#     api_spec_url='/spec'
# )
###################################

api.add_resource(RootR, "/")
api.add_resource(CoprListR, "/coprs")
api.add_resource(CoprR, "/coprs/<owner>/<project>")

api.add_resource(ChrootListR, "/chroots")
api.add_resource(ChrootR, "/chroots/<name>")

api.add_resource(BuildListR, "/builds")
api.add_resource(BuildR, "/builds/<int:build_id>")

# app.register_blueprint(rest_api_bp, url_prefix=URL_PREFIX)


# TODO: try: https://github.com/sloria/flask-marshmallow
def register_api_error_handler(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        response = Response(
            response="{}\n".format(error.data),
            status=error.code,
            mimetype="text/plain",
            headers=error.headers,
        )
        return response
