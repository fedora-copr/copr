import flask
import wtforms
from . import optional_params, get_copr, Paginator, BaseListForm
from coprs import models
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic


class PackageListForm(BaseListForm):
    ownername = wtforms.StringField("Ownername")
    projectname = wtforms.StringField("Projectname")


@apiv3_ns.route("/package/list/", methods=["GET"])
@optional_params(PackageListForm)
def get_package_list(**kwargs):
    copr = get_copr()
    paginator = Paginator(PackagesLogic.get_all(copr.id), models.Package, **kwargs)
    packages = paginator.to_dict()
    # @FIXME we have a source_json field which is a string. We should rather transform it into source dict
    return flask.jsonify(items=packages, meta=paginator.meta)
