import flask
import sqlalchemy
from requests.exceptions import RequestException, InvalidSchema
from wtforms import ValidationError
from . import query_params, get_copr, file_upload, POST
from coprs import db, models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.views.misc import api_login_required
from coprs.exceptions import ApiError, DuplicateException, BadRequest
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
    form = forms.ModuleBuildForm(csrf_enabled=False)
    if not form.validate_on_submit():
        raise BadRequest(form.errors)

    facade = None
    try:
        mod_info = ModuleProvider.from_input(form.modulemd.data or form.scmurl.data)
        facade = ModuleBuildFacade(flask.g.user, copr, mod_info.yaml, mod_info.filename)
        module = facade.submit_build()
        db.session.commit()
        return flask.jsonify(to_dict(module))

    except (ValidationError, RequestException, InvalidSchema) as ex:
        raise BadRequest(str(ex))

    except sqlalchemy.exc.IntegrityError:
        raise DuplicateException("Module {}-{}-{} already exists".format(
                                 facade.modulemd.name, facade.modulemd.stream, facade.modulemd.version))
