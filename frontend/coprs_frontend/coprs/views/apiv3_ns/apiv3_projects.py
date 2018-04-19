import os
import flask
from . import query_params, get_copr, pagination, Paginator
from coprs import db, models, forms
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import fix_protocol_for_backend
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
        "yum_repos": {},
        "description": copr.description,
        "instructions": copr.instructions,
        "last_modified": BuildsLogic.last_modified(copr),
        "auto_createrepo": copr.auto_createrepo,
        "persistent": copr.persistent,
        "unlisted_on_hp": copr.unlisted_on_hp,
        "auto_prune": copr.auto_prune,
        "use_bootstrap_container": copr.use_bootstrap_container,
    }

    # @TODO find a better place for yum_repos logic
    release_tmpl = "{chroot.os_release}-{chroot.os_version}-{chroot.arch}"
    build = models.Build.query.filter(models.Build.copr_id == copr.id).first()
    if build:
        for chroot in copr.active_chroots:
            release = release_tmpl.format(chroot=chroot)
            copr_dict["yum_repos"][release] = fix_protocol_for_backend(
                os.path.join(build.copr.repo_url, release + '/'))

    return copr_dict


def get_copr_form_factory():
    form = forms.CoprFormFactory.create_form_cls()(csrf_enabled=False)
    for chroot in form.chroots_list:
        if chroot in flask.request.json["chroots"]:
            getattr(form, chroot).data = True
    return form


@apiv3_ns.route("/project", methods=["GET"])
@query_params()
def get_project(ownername, projectname):
    copr = get_copr()
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


@apiv3_ns.route("/project/add", methods=["POST"])
@api_login_required
@query_params()
def add_project(ownername):
    form = get_copr_form_factory()

    # @TODO rather raise exeptions in the validate_post_keys
    # are there any arguments in POST which our form doesn't know?
    # infos.extend(validate_post_keys(form))

    if not form.validate_on_submit():
        raise ApiError(form.errors)

    # @TODO move this logic somewhere else
    group = None
    if ownername[0] == "@":
        group = ComplexLogic.get_group_by_name_safe(ownername[1:])

    try:
        copr = CoprsLogic.add(
            name=form.name.data.strip(),
            repos=" ".join(form.repos.data.split()),  # @TODO we should send the repos as list, not string
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
    copr = get_copr()
    form = forms.CoprModifyForm(csrf_enabled=False)

    if not form.validate_on_submit():
        raise ApiError("Invalid request: {0}".format(form.errors))

    for field in form:
        if field.data is None or field.name in ["csrf_token", "chroots"]:
            continue
        setattr(copr, field.name, field.data)

    # @TODO we should send chroots as a list not string
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
            NonAdminCannotDisableAutoPrunning) as e:
        db.session.rollback()
        raise ApiError("Invalid request: {}".format(e))

    return flask.jsonify(to_dict(copr))
