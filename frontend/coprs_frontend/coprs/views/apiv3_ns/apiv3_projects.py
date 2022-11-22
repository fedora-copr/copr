import flask
from coprs.views.apiv3_ns import (query_params, get_copr, pagination, Paginator,
                                  GET, POST, PUT, DELETE, set_defaults)
from coprs.views.apiv3_ns.json2form import get_form_compatible_data, get_input_dict
from coprs import db, models, forms, db_session_scope
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic, MockChrootsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic
from coprs.exceptions import (DuplicateException, NonAdminCannotCreatePersistentProject,
                              NonAdminCannotDisableAutoPrunning, ActionInProgressException,
                              InsufficientRightsException, BadRequest, ObjectNotFound,
                              InvalidForm)
from . import editable_copr


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
        "bootstrap": copr.bootstrap,
        "isolation": copr.isolation,
        "module_hotfixes": copr.module_hotfixes,
        "appstream": copr.appstream,
        "packit_forge_projects_allowed": copr.packit_forge_projects_allowed_list,
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
    inserted = set(input.get("chroots") or [])
    allowed = {x.name for x in allowed_chroots}
    unexpected = inserted - allowed
    if unexpected:
        raise BadRequest("Unexpected chroot: {}".format(", ".join(unexpected)))


def owner2tuple(ownername):
    """
    This function takes `ownername` on its input. That can be either some
    username or a group name starting with @ character. Then it returns a tuple
    of two objects - `models.User` and `models.Group`.

    Every project (even a group one) needs to have some user assigned to it, so
    this value will always be some user object. Group can obviously be `None`.
    """
    user = flask.g.user
    group = None
    if ownername[0] == "@":
        group = ComplexLogic.get_group_by_name_safe(ownername[1:])
    elif ownername != flask.g.user.name:
        user = UsersLogic.get(ownername).first()
    if not user:
        raise ObjectNotFound("No such user `{0}'".format(ownername))
    return user, group


@apiv3_ns.route("/project", methods=GET)
@query_params()
def get_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    return flask.jsonify(to_dict(copr))


@apiv3_ns.route("/project/list", methods=GET)
@pagination()
@query_params()
def get_project_list(ownername=None, **kwargs):
    query = CoprsLogic.get_multiple()
    if ownername:
        query = CoprsLogic.filter_by_ownername(query, ownername)
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
    user, group = owner2tuple(ownername)
    data = rename_fields(get_form_compatible_data(preserve=["chroots"]))
    form_class = forms.CoprFormFactory.create_form_cls(user=user, group=group)
    set_defaults(data, form_class)
    form = form_class(data, meta={'csrf': False})

    if not form.validate_on_submit():
        raise InvalidForm(form)
    validate_chroots(get_input_dict(), MockChrootsLogic.get_multiple())

    bootstrap = None
    # backward compatibility
    use_bootstrap_container = form.use_bootstrap_container.data
    if use_bootstrap_container is not None:
        bootstrap = "on" if use_bootstrap_container else "off"
    if form.bootstrap.data is not None:
        bootstrap = form.bootstrap.data

    try:

        def _form_field_repos(form_field):
            return " ".join(form_field.data.split())

        copr = CoprsLogic.add(
            name=form.name.data.strip(),
            repos=_form_field_repos(form.repos),
            user=user,
            selected_chroots=form.selected_chroots,
            description=form.description.data,
            instructions=form.instructions.data,
            check_for_duplicates=True,
            unlisted_on_hp=form.unlisted_on_hp.data,
            build_enable_net=form.enable_net.data,
            group=group,
            persistent=form.persistent.data,
            auto_prune=form.auto_prune.data,
            bootstrap=bootstrap,
            isolation=form.isolation.data,
            homepage=form.homepage.data,
            contact=form.contact.data,
            disable_createrepo=form.disable_createrepo.data,
            delete_after_days=form.delete_after_days.data,
            multilib=form.multilib.data,
            module_hotfixes=form.module_hotfixes.data,
            fedora_review=form.fedora_review.data,
            follow_fedora_branching=form.follow_fedora_branching.data,
            runtime_dependencies=_form_field_repos(form.runtime_dependencies),
            appstream=form.appstream.data,
            packit_forge_projects_allowed=_form_field_repos(form.packit_forge_projects_allowed),
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
    data = rename_fields(get_form_compatible_data(preserve=["chroots"]))
    form = forms.CoprForm(data, meta={'csrf': False})

    if not form.validate_on_submit():
        raise InvalidForm(form)
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
    data = get_form_compatible_data(preserve=["chroots"])
    data["owner"] = data.get("ownername")

    form = forms.CoprForkFormFactory \
        .create_form_cls(copr=copr, user=flask.g.user, groups=flask.g.user.user_groups)(data, meta={'csrf': False})

    if form.validate_on_submit() and copr:
        try:
            dstgroup = ([g for g in flask.g.user.user_groups if g.at_name == form.owner.data] or [None])[0]
            if flask.g.user.name != form.owner.data and not dstgroup:
                return ObjectNotFound("There is no such group: {}".format(form.owner.data))

            dst_copr = CoprsLogic.get(flask.g.user.name, form.name.data).all()
            if dst_copr and form.confirm.data != True:
                raise BadRequest("You are about to fork into existing project: {}\n"
                                 "Please use --confirm if you really want to do this".format(form.name.data))
            fcopr, _ = ComplexLogic.fork_copr(copr, flask.g.user, dstname=form.name.data,
                                              dstgroup=dstgroup)
            db.session.commit()

        except (ActionInProgressException, InsufficientRightsException) as err:
            db.session.rollback()
            raise err
    else:
        raise InvalidForm(form)

    return flask.jsonify(to_dict(fcopr))


@apiv3_ns.route("/project/delete/<ownername>/<projectname>", methods=DELETE)
@api_login_required
def delete_project(ownername, projectname):
    copr = get_copr(ownername, projectname)
    copr_dict = to_dict(copr)
    form = forms.APICoprDeleteForm(meta={'csrf': False})

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
        raise InvalidForm(form)
    return flask.jsonify(copr_dict)

@apiv3_ns.route("/project/regenerate-repos/<ownername>/<projectname>", methods=PUT)
@api_login_required
@editable_copr
def regenerate_repos(copr):
    """
    This function will regenerate all repository metadata for a project.
    """
    with db_session_scope():
        ActionsLogic.send_createrepo(copr, devel=False)

    return flask.jsonify(to_dict(copr))
