import flask
import sqlalchemy
from requests.exceptions import RequestException, InvalidSchema
from wtforms import ValidationError
from coprs import forms, db_session_scope
from coprs.views.apiv3_ns import apiv3_ns, get_copr, file_upload, POST
from coprs.views.misc import api_login_required
from coprs.exceptions import DuplicateException, BadRequest, InvalidForm
from coprs.logic.modules_logic import ModuleProvider, ModuleBuildFacade


def to_dict(module):
    return {
        "nsv": module.nsv,
    }


@apiv3_ns.route("/module/build/<ownername>/<projectname>", methods=POST)
@api_login_required
@file_upload()
def build_module(ownername, projectname):
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
        return flask.jsonify(to_dict(module))

    except (ValidationError, RequestException, InvalidSchema, RuntimeError) as ex:
        raise BadRequest(str(ex)) from ex

    except sqlalchemy.exc.IntegrityError as err:
        raise DuplicateException("Module {}-{}-{} already exists"
                                 .format(facade.modulemd.get_module_name(),
                                         facade.modulemd.get_stream_name(),
                                         facade.modulemd.get_version())) from err
