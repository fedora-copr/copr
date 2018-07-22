import os
import flask
from . import query_params, get_copr, pagination, Paginator, GET, POST, PUT, DELETE
from .json2form import get_form_compatible_data, get_input_dict
from coprs import db, models, forms
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic, MockChrootsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.exceptions import (ApiError, DuplicateException, NonAdminCannotCreatePersistentProject,
                              NonAdminCannotDisableAutoPrunning, ActionInProgressException,
                              InsufficientRightsException, BadRequest, ObjectNotFound)


def to_dict(copr):
    return {
        "id": copr.id,
        "name": copr.name,
        "ownername": copr.owner_name,
        "full_name": copr.full_name,
        "homepage": copr.homepage,
        "contact": copr.contact,
        "description": copr.description,
        "instructions": copr.instructions,
        "devel_mode": copr.devel_mode,
        "persistent": copr.persistent,
        "unlisted_on_hp": copr.unlisted_on_hp,
        "auto_prune": copr.auto_prune,
        "chroot_repos": CoprsLogic.get_yum_repos(copr, empty=True),
        "additional_repos": copr.repos_list,
        "enable_net": copr.build_enable_net,
        "use_bootstrap_container": copr.use_bootstrap_container,
    }


def rename_fields(input):
    replace = {
        "devel_mode": "disable_createrepo",
        "additional_repos": "repos",
    }
    output = input.copy()
    for from_name, to_name in replace.items():
        if from_name not in output:
            continue
        output[to_name] = output.pop(from_name)
    return output


def validate_chroots(input, allowed_chroots):
    inserted = set(input["chroots"] or [])
    allowed = {x.name for x in allowed_chroots}
    unexpected = inserted - allowed
    if unexpected:
        raise BadRequest("Unexpected chroot: {}".format(", ".join(unexpected)))


@apiv3_ns.route("/project", methods=GET)
@query_params()
def get_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/list", methods=GET)
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


@apiv3_ns.route("/project/search", methods=GET)
@pagination()
@query_params()
# @TODO should the param be query or projectname?
def search_projects(query, **kwargs):
    try:
        search_query = CoprsLogic.get_multiple_fulltext(query)
        paginator = Paginator(search_query, models.Copr, **kwargs)
        projects = paginator.map(to_dict)
    except ValueError as ex:
        raise BadRequest(str(ex))
    return flask.jsonify(items=projects, meta=paginator.meta)


@apiv3_ns.route("/project/add/<ownername>", methods=POST)
@api_login_required
def add_project(ownername):
    data = rename_fields(get_form_compatible_data())
    form = forms.CoprFormFactory.create_form_cls()(data, csrf_enabled=False)

    if not form.validate_on_submit():
        raise BadRequest(form.errors)
    validate_chroots(get_input_dict(), MockChrootsLogic.get_multiple())

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
            unlisted_on_hp=form.unlisted_on_hp.data,
            build_enable_net=form.enable_net.data,
            group=group,
            persistent=form.persistent.data,
            auto_prune=form.auto_prune.data,
            use_bootstrap_container=form.use_bootstrap_container.data,
            homepage=form.homepage.data,
            contact=form.contact.data,
        )
        db.session.commit()
    except (DuplicateException,
            NonAdminCannotCreatePersistentProject,
            NonAdminCannotDisableAutoPrunning) as err:
        db.session.rollback()
        raise err
    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/edit/<ownername>/<projectname>", methods=PUT)
@api_login_required
def edit_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    data = rename_fields(get_form_compatible_data())
    form = forms.CoprModifyForm(data, csrf_enabled=False)

    if not form.validate_on_submit():
        raise BadRequest(form.errors)
    validate_chroots(get_input_dict(), MockChrootsLogic.get_multiple())

    for field in form:
        if field.data is None or field.name in ["csrf_token", "chroots"]:
            continue
        if field.name not in data.keys():
            continue
        setattr(copr, field.name, field.data)

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
        raise ex

    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/fork/<ownername>/<projectname>", methods=PUT)
@api_login_required
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
                return ObjectNotFound("There is no such group: {}".format(form.owner.data))

            fcopr, created = ComplexLogic.fork_copr(copr, flask.g.user, dstname=form.name.data, dstgroup=dstgroup)
            if not created and form.confirm.data != True:
                raise BadRequest("You are about to fork into existing project: {}\n"
                                 "Please use --confirm if you really want to do this".format(fcopr.full_name))
            db.session.commit()

        except (ActionInProgressException, InsufficientRightsException) as err:
            db.session.rollback()
            raise err
    else:
        raise BadRequest(form.errors)

    return flask.jsonify(to_dict(fcopr))


@apiv3_ns.route("/project/delete/<ownername>/<projectname>", methods=DELETE)
@api_login_required
def delete_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    form = forms.APICoprDeleteForm(csrf_enabled=False)

    if form.validate_on_submit() and copr:
        try:
            ComplexLogic.delete_copr(copr)
        except (ActionInProgressException,
                InsufficientRightsException) as err:
            db.session.rollback()
            raise err
        else:
            db.session.commit()
    else:
        raise BadRequest(form.errors)
    return flask.jsonify(to_dict(copr))
