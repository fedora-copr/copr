import os
import flask
from . import query_params, get_copr, pagination, Paginator
from .json2form import get_form_compatible_data
from coprs import db, models, forms
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.exceptions import (ApiError, DuplicateException, NonAdminCannotCreatePersistentProject,
                              NonAdminCannotDisableAutoPrunning, ActionInProgressException,
                              InsufficientRightsException)


def to_dict(copr):
    # @TODO review the fields
    copr_dict = {
        "name": copr.name,
        "owner": copr.owner_name,
        "full_name": copr.full_name,
        "additional_repos": copr.repos,
        "yum_repos": CoprsLogic.get_yum_repos(copr),
        "description": copr.description,
        "instructions": copr.instructions,
        "last_modified": BuildsLogic.last_modified(copr),
        "auto_createrepo": copr.auto_createrepo,
        "persistent": copr.persistent,
        "unlisted_on_hp": copr.unlisted_on_hp,
        "auto_prune": copr.auto_prune,
        "use_bootstrap_container": copr.use_bootstrap_container,
    }
    return copr_dict


@apiv3_ns.route("/project", methods=["GET"])
@query_params()
def get_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/list", methods=["GET"])
@pagination()
@query_params()
def get_project_list(ownername, **kwargs):
    if ownername.startswith("@"):
        group_name = ownername[1:]
        query = CoprsLogic.get_multiple()
        query = CoprsLogic.filter_by_group_name(query, group_name)
    else:
        query = CoprsLogic.get_multiple_owned_by_username(ownername)

    # @TODO ordering doesn't work correctly - try order by models.Copr.name DESC
    paginator = Paginator(query, models.Copr, **kwargs)
    projects = paginator.map(to_dict)
    return flask.jsonify(items=projects, meta=paginator.meta)


@apiv3_ns.route("/project/search", methods=["GET"])
@pagination()
@query_params()
# @TODO should the param be query or projectname?
def search_projects(query, **kwargs):
    try:
        search_query = CoprsLogic.get_multiple_fulltext(query)
        paginator = Paginator(search_query, models.Copr, **kwargs)
        projects = paginator.map(to_dict)
    except ValueError as ex:
        raise ApiError("Server error: {}".format(ex))
    return flask.jsonify(items=projects, meta=paginator.meta)


@apiv3_ns.route("/project/add", methods=["POST"])
@api_login_required
@query_params()
def add_project(ownername):
    data = get_form_compatible_data()
    form = forms.CoprFormFactory.create_form_cls()(data, csrf_enabled=False)

    if not form.validate_on_submit():
        raise ApiError(form.errors)

    group = None
    if ownername[0] == "@":
        group = ComplexLogic.get_group_by_name_safe(ownername[1:])

    try:
        copr = CoprsLogic.add(
            name=form.name.data.strip(),
            repos=" ".join(form.repos.data.split()),
            user=flask.g.user,
            selected_chroots=form.selected_chroots,
            description=form.description.data,
            instructions=form.instructions.data,
            check_for_duplicates=True,
            disable_createrepo=form.disable_createrepo.data,
            unlisted_on_hp=form.unlisted_on_hp.data,
            build_enable_net=form.build_enable_net.data,
            group=group,
            persistent=form.persistent.data,
            auto_prune=form.auto_prune.data,
            use_bootstrap_container=form.use_bootstrap_container.data,
        )
        db.session.commit()
    except (DuplicateException,
            NonAdminCannotCreatePersistentProject,
            NonAdminCannotDisableAutoPrunning) as err:
        db.session.rollback()
        raise ApiError(str(err))
    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/edit", methods=["POST"])
@api_login_required
@query_params()
def edit_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    data = get_form_compatible_data()
    form = forms.CoprModifyForm(data, csrf_enabled=False)

    if not form.validate_on_submit():
        raise ApiError(form.errors)

    for key, value in data.items():
        if key in ["csrf_token", "chroots"]:
            continue
        setattr(copr, key, value)

    if form.chroots.data:
        CoprChrootsLogic.update_from_names(
            flask.g.user, copr, form.chroots.data)

    try:
        CoprsLogic.update(flask.g.user, copr)
        if copr.group: # load group.id
            _ = copr.group.id
        db.session.commit()
    except (ActionInProgressException,
            InsufficientRightsException,
            NonAdminCannotDisableAutoPrunning) as ex:
        db.session.rollback()
        raise ApiError(str(ex))

    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/fork", methods=["POST"])
@api_login_required
@query_params()
def fork_project(ownername, projectname):
    copr = get_copr(ownername, projectname)

    # @FIXME we want "ownername" from the outside, but our internal Form expects "owner" instead
    data = get_form_compatible_data()
    data["owner"] = data.get("ownername")

    form = forms.CoprForkFormFactory \
        .create_form_cls(copr=copr, user=flask.g.user, groups=flask.g.user.user_groups)(data, csrf_enabled=False)

    if form.validate_on_submit() and copr:
        try:
            dstgroup = ([g for g in flask.g.user.user_groups if g.at_name == form.owner.data] or [None])[0]
            if flask.g.user.name != form.owner.data and not dstgroup:
                return ApiError("There is no such group: {}".format(form.owner.data))

            fcopr, created = ComplexLogic.fork_copr(copr, flask.g.user, dstname=form.name.data, dstgroup=dstgroup)
            if not created and form.confirm.data != True:
                raise ApiError("You are about to fork into existing project: {}\n"
                               "Please use --confirm if you really want to do this".format(fcopr.full_name))
            db.session.commit()

        except (ActionInProgressException, InsufficientRightsException) as err:
            db.session.rollback()
            raise ApiError(str(err))
    else:
        raise ApiError(form.errors)

    return flask.jsonify(to_dict(fcopr))


@apiv3_ns.route("/project/delete", methods=["POST"])
@api_login_required
@query_params()
def delete_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    form = forms.APICoprDeleteForm(csrf_enabled=False)

    if form.validate_on_submit() and copr:
        try:
            ComplexLogic.delete_copr(copr)
        except (ActionInProgressException,
                InsufficientRightsException) as err:
            db.session.rollback()
            raise ApiError(str(err))
        else:
            db.session.commit()
    else:
        raise ApiError(form.errors)
    return flask.jsonify(to_dict(copr))
