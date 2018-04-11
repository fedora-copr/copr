import flask
import wtforms
from . import optional_params, query_params, get_copr, Paginator, BaseListForm
from coprs.exceptions import ApiError
from coprs.views.misc import api_login_required
from coprs import models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic


# @TODO Don't import things from APIv1
from coprs.views.api_ns.api_general import process_package_add_or_edit


def to_dict(package):
    # @TODO review the fields
    api_keys = ["id", "name", "enable_net", "old_status", "source_type", "webhook_rebuild"]
    package_dict = {k: v for k, v in package.to_dict().items() if k in api_keys}
    package_dict.update({
        "copr": package.copr.name,
        "owner": package.copr.owner_name,
        "source": package.source_json_dict,
    })
    return package_dict


class PackageListForm(BaseListForm):
    ownername = wtforms.StringField("Ownername")
    projectname = wtforms.StringField("Projectname")


@apiv3_ns.route("/package", methods=["GET"])
@query_params()
def get_package(ownername, projectname, packagename):
    copr = get_copr()
    try:
        package = PackagesLogic.get(copr.id, packagename)[0]
    except IndexError:
        raise ApiError("No package with name {name} in copr {copr}".format(name=packagename, copr=copr.name))
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/list/", methods=["GET"])
@optional_params(PackageListForm)
def get_package_list(**kwargs):
    copr = get_copr()
    paginator = Paginator(PackagesLogic.get_all(copr.id), models.Package, **kwargs)
    packages = paginator.map(to_dict)
    return flask.jsonify(items=packages, meta=paginator.meta)


@apiv3_ns.route("/package/edit", methods=["POST"])
@api_login_required
def package_edit():
    copr = get_copr()
    form = forms.PackageTypeSelectorForm()
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ApiError("Package {name} does not exists in copr {copr}."
                             .format(name=form.package_name.data, copr=copr.full_name))

    process_package_add_or_edit(copr, form.source_type_text.data, package=package)
    return flask.jsonify(to_dict(package))
