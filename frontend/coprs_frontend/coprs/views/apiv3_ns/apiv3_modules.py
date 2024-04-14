# pylint: disable=missing-class-docstring


from http import HTTPStatus

import flask
import sqlalchemy
from flask_restx import Namespace, Resource
from requests.exceptions import RequestException, InvalidSchema
from wtforms import ValidationError

from coprs import forms, db_session_scope
from coprs.views.apiv3_ns import api, get_copr, file_upload
from coprs.views.apiv3_ns.schema.schemas import (module_build_model, fullname_params,
                                                 module_add_input_model)
from coprs.views.misc import api_login_required
from coprs.exceptions import DuplicateException, BadRequest, InvalidForm
from coprs.logic.modules_logic import ModuleProvider, ModuleBuildFacade


apiv3_module_ns = Namespace("module", description="Module")
api.add_namespace(apiv3_module_ns)


def to_dict(module):
    return {
        "nsv": module.nsv,
    }


@apiv3_module_ns.route("/build/<ownername>/<projectname>")
class Module(Resource):
    @api_login_required
    @file_upload
    @apiv3_module_ns.doc(params=fullname_params)
    @apiv3_module_ns.expect(module_add_input_model)
    @apiv3_module_ns.marshal_with(module_build_model)
    @apiv3_module_ns.response(HTTPStatus.OK.value, "Module build successfully submitted")
    @apiv3_module_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, ownername, projectname):
        """
        Create a module build
        Create a module build for ownername/projectname project.
        """
        copr = get_copr(ownername, projectname)
        form = forms.get_module_build_form(meta={'csrf': False})
        if not form.validate_on_submit():
            raise InvalidForm(form)

        facade = None
        try:
            mod_info = ModuleProvider.from_input(form.modulemd.data or form.scmurl.data)
            facade = ModuleBuildFacade(flask.g.user, copr, mod_info.yaml,
                                       mod_info.filename, form.distgit.data)
            with db_session_scope():
                module = facade.submit_build()
            return to_dict(module)

        except (ValidationError, RequestException, InvalidSchema, RuntimeError) as ex:
            raise BadRequest(str(ex)) from ex

        except sqlalchemy.exc.IntegrityError as err:
            raise DuplicateException("Module {}-{}-{} already exists"
                                     .format(facade.modulemd.get_module_name(),
                                             facade.modulemd.get_stream_name(),
                                             facade.modulemd.get_version())) from err
