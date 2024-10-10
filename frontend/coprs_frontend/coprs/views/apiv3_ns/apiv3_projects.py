# pylint: disable=missing-class-docstring

from http import HTTPStatus

import flask

from flask_restx import Namespace, Resource
from sqlalchemy.exc import IntegrityError

from coprs.views.apiv3_ns import (
    get_copr,
    pagination,
    Paginator,
    set_defaults,
    deprecated_route_method_type,
    editable_copr,
)
from coprs.views.apiv3_ns.json2form import get_form_compatible_data, get_input_dict
from coprs import app, db, models, forms, db_session_scope
from coprs.views.misc import api_login_required
from coprs.views.apiv3_ns import rename_fields_helper, api, query_to_parameters
from coprs.views.apiv3_ns.schema.schemas import (
    project_model,
    project_add_input_model,
    project_edit_input_model,
    project_fork_input_model,
    project_delete_input_model,
    fullname_params,
    pagination_project_model,
    project_params,
    pagination_params,
)
from coprs.views.apiv3_ns.schema.docs import query_docs
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic, MockChrootsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic
from coprs.exceptions import (
    DuplicateException,
    NonAdminCannotCreatePersistentProject,
    NonAdminCannotDisableAutoPrunning,
    ActionInProgressException,
    InsufficientRightsException,
    BadRequest,
    ObjectNotFound,
    InvalidForm,
)


apiv3_projects_ns = Namespace("project", description="Projects")
api.add_namespace(apiv3_projects_ns)


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
        "follow_fedora_branching": copr.follow_fedora_branching,
        "repo_priority": copr.repo_priority,
        # TODO: unify projectname and name or (good luck) force marshaling to work
        #  without it. Marshaling tries to create a docs page for the endpoint to
        #  HTML with argument names the same as they are defined in methods
        #  but we have this inconsistency between name - projectname
        "projectname": copr.name,
    }


def rename_fields(input_dict):
    return rename_fields_helper(input_dict, {
        "devel_mode": "disable_createrepo",
        "additional_repos": "repos",
    })


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
        group = ComplexLogic.get_group_by_name(ownername[1:])
    elif ownername != flask.g.user.name:
        user = UsersLogic.get(ownername).first()
    if not user:
        raise ObjectNotFound("No such user `{0}'".format(ownername))
    return user, group


@apiv3_projects_ns.route("/")
class Project(Resource):
    @query_to_parameters
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "OK, Project data follows...")
    @apiv3_projects_ns.response(
        HTTPStatus.NOT_FOUND.value, "No such Copr project found in database"
    )
    def get(self, ownername, projectname):
        """
        Get a project
        Get details for a single Copr project according to ownername and projectname.
        """
        copr = get_copr(ownername, projectname)
        return to_dict(copr)


@apiv3_projects_ns.route("/list")
class ProjectList(Resource):
    @pagination
    @query_to_parameters
    @apiv3_projects_ns.doc(params=project_params | pagination_params)
    @apiv3_projects_ns.marshal_list_with(pagination_project_model)
    @apiv3_projects_ns.response(
        HTTPStatus.PARTIAL_CONTENT.value, HTTPStatus.PARTIAL_CONTENT.description
    )
    def get(self, ownername=None, **kwargs):
        """
        Get list of projects
        Get details for multiple Copr projects according to ownername
        """
        query = CoprsLogic.get_multiple()
        if ownername:
            query = CoprsLogic.filter_by_ownername(query, ownername)
        paginator = Paginator(query, models.Copr, **kwargs)
        projects = paginator.map(to_dict)
        return {"items": projects, "meta": paginator.meta}


@apiv3_projects_ns.route("/search")
class ProjectSearch(Resource):
    @pagination
    @query_to_parameters
    @apiv3_projects_ns.doc(params=query_docs)
    @apiv3_projects_ns.marshal_list_with(pagination_project_model)
    @apiv3_projects_ns.response(
        HTTPStatus.PARTIAL_CONTENT.value, HTTPStatus.PARTIAL_CONTENT.description
    )
    # TODO: should the param be query or projectname?
    def get(self, query, **kwargs):
        """
        Get list of projects
        Get details for multiple Copr projects according to search query.
        """
        try:
            search_query = CoprsLogic.get_multiple_fulltext(query)
            paginator = Paginator(search_query, models.Copr, **kwargs)
            projects = paginator.map(to_dict)
        except ValueError as ex:
            raise BadRequest(str(ex)) from ex
        return {"items": projects, "meta": paginator.meta}


@apiv3_projects_ns.route("/add/<ownername>")
class ProjectAdd(Resource):
    @api_login_required
    @query_to_parameters
    @apiv3_projects_ns.doc(params=project_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_add_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Copr project created")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, ownername, exist_ok=False):
        """
        Create new Copr project
        Create new Copr project for ownername with specified data inserted in form.
        """
        exist_ok = flask.request.args.get("exist_ok") == "True"
        user, group = owner2tuple(ownername)
        data = rename_fields(get_form_compatible_data(preserve=["chroots"]))
        form_class = forms.CoprFormFactory.create_form_cls(user=user, group=group,
                                                           exist_ok=exist_ok)
        set_defaults(data, form_class)
        form = form_class(data, meta={"csrf": False})

        if not form.validate_on_submit():
            if exist_ok:
                # This is an ugly hack to avoid additional database query.
                # If a project with this owner and name already exists, the
                # `CoprUniqueNameValidator` saved its instance. Let's find the
                # validator and return the existing copr instance.
                for validator in form.name.validators:
                    if not isinstance(validator, forms.CoprUniqueNameValidator):
                        continue
                    if not validator.copr:
                        continue
                    return to_dict(validator.copr)
            raise InvalidForm(form)
        validate_chroots(get_input_dict(), MockChrootsLogic.get_multiple())

        bootstrap = None
        # backward compatibility
        use_bootstrap_container = form.use_bootstrap_container.data
        if use_bootstrap_container is not None:
            bootstrap = "on" if use_bootstrap_container else "off"
        if form.bootstrap.data is not None:
            bootstrap = form.bootstrap.data

        projectname = form.name.data.strip()
        try:

            def _form_field_repos(form_field):
                return " ".join(form_field.data.split())

            copr = CoprsLogic.add(
                name=projectname,
                repos=_form_field_repos(form.repos),
                user=user,
                selected_chroots=form.selected_chroots,
                description=form.description.data,
                instructions=form.instructions.data,
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
                packit_forge_projects_allowed=_form_field_repos(
                    form.packit_forge_projects_allowed
                ),
                repo_priority=form.repo_priority.data,
                storage=form.storage.data,
            )
            db.session.commit()
        except IntegrityError as ierr:
            app.logger.debug("Racy attempt to create %s/%s", ownername, projectname)
            db.session.rollback()
            if exist_ok:
                copr = get_copr(ownername, projectname)
                return to_dict(copr)
            raise DuplicateException(
                f"Copr '{ownername}/{projectname}' has not been created "
                "(race condition)"
            ) from ierr
        except (
            DuplicateException,  # TODO: can this happen? and exist_ok?
            NonAdminCannotCreatePersistentProject,
            NonAdminCannotDisableAutoPrunning,
        ) as err:
            db.session.rollback()
            raise err

        return to_dict(copr)


@apiv3_projects_ns.route("/edit/<ownername>/<projectname>")
class ProjectEdit(Resource):
    @staticmethod
    def _common(ownername, projectname):
        copr = get_copr(ownername, projectname)
        data = rename_fields(get_form_compatible_data(preserve=["chroots"]))
        form = forms.CoprForm(data, meta={"csrf": False})

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
            CoprChrootsLogic.update_from_names(flask.g.user, copr, form.chroots.data)

        try:
            CoprsLogic.update(flask.g.user, copr)
            if copr.group:  # load group.id
                _ = copr.group.id
            db.session.commit()
        except (
            ActionInProgressException,
            InsufficientRightsException,
            NonAdminCannotDisableAutoPrunning,
        ) as ex:
            db.session.rollback()
            raise ex

        return to_dict(copr)

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_edit_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Copr project successfully edited")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def put(self, ownername, projectname):
        """
        Edit Copr project
        Edit existing Copr project for ownername/projectname in form.
        """
        return self._common(ownername, projectname)

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_edit_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Copr project successfully edited")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    @deprecated_route_method_type(apiv3_projects_ns, "POST", "PUT")
    def post(self, ownername, projectname):
        """
        Edit Copr project
        Edit existing Copr project for ownername/projectname in form.
        """
        return self._common(ownername, projectname)


@apiv3_projects_ns.route("/fork/<ownername>/<projectname>")
class ProjectFork(Resource):
    @staticmethod
    def _common(ownername, projectname):
        copr = get_copr(ownername, projectname)

        # @FIXME we want "ownername" from the outside, but our internal Form expects "owner" instead
        data = get_form_compatible_data(preserve=["chroots"])
        data["owner"] = data.get("ownername")

        form = forms.CoprForkFormFactory.create_form_cls(
            copr=copr, user=flask.g.user, groups=flask.g.user.user_groups
        )(data, meta={"csrf": False})

        if form.validate_on_submit() and copr:
            try:
                dstgroup = (
                    [
                        g
                        for g in flask.g.user.user_groups
                        if g.at_name == form.owner.data
                    ]
                    or [None]
                )[0]
                if flask.g.user.name != form.owner.data and not dstgroup:
                    return ObjectNotFound(
                        "There is no such group: {}".format(form.owner.data)
                    )

                dst_copr = CoprsLogic.get(flask.g.user.name, form.name.data).all()
                if dst_copr and not form.confirm.data:
                    raise BadRequest(
                        "You are about to fork into existing project: {}\n"
                        "Please use --confirm if you really want to do this".format(
                            form.name.data
                        )
                    )
                fcopr, _ = ComplexLogic.fork_copr(
                    copr, flask.g.user, dstname=form.name.data, dstgroup=dstgroup
                )
                db.session.commit()

            except (ActionInProgressException, InsufficientRightsException) as err:
                db.session.rollback()
                raise err
        else:
            raise InvalidForm(form)

        return to_dict(fcopr)

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_fork_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Copr project is forking...")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def post(self, ownername, projectname):
        """
        Fork Copr project
        Fork Copr project for specified ownername/projectname insto your namespace.
        """
        return self._common(ownername, projectname)

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_fork_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Copr project is forking...")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    @deprecated_route_method_type(apiv3_projects_ns, "PUT", "POST")
    def put(self, ownername, projectname):
        """
        Fork Copr project
        Fork Copr project for specified ownername/projectname insto your namespace.
        """
        return self._common(ownername, projectname)


@apiv3_projects_ns.route("/delete/<ownername>/<projectname>")
class ProjectDelete(Resource):
    @staticmethod
    def _common(ownername, projectname):
        copr = get_copr(ownername, projectname)
        copr_dict = to_dict(copr)
        form = forms.APICoprDeleteForm(meta={"csrf": False})

        if form.validate_on_submit() and copr:
            try:
                ComplexLogic.delete_copr(copr)
            except (ActionInProgressException, InsufficientRightsException) as err:
                db.session.rollback()
                raise err

            db.session.commit()
        else:
            raise InvalidForm(form)
        return copr_dict

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_delete_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Project successfully deleted")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    def delete(self, ownername, projectname):
        """
        Delete Copr project
        Delete specified ownername/projectname Copr project forever.
        """
        return self._common(ownername, projectname)

    @api_login_required
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.expect(project_delete_input_model)
    @apiv3_projects_ns.response(HTTPStatus.OK.value, "Project successfully deleted")
    @apiv3_projects_ns.response(
        HTTPStatus.BAD_REQUEST.value, HTTPStatus.BAD_REQUEST.description
    )
    @deprecated_route_method_type(apiv3_projects_ns, "POST", "DELETE")
    def post(self, ownername, projectname):
        """
        Delete Copr project
        Delete specified ownername/projectname Copr project forever.
        """
        return self._common(ownername, projectname)


@apiv3_projects_ns.route("/regenerate-repos/<ownername>/<projectname>")
class RegenerateRepos(Resource):
    @staticmethod
    def _common(copr):
        with db_session_scope():
            ActionsLogic.send_createrepo(copr, devel=False)

        return to_dict(copr)

    @api_login_required
    @editable_copr
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.response(
        HTTPStatus.OK.value, "OK, reposirory metadata regenerated"
    )
    def put(self, copr):
        """
        Regenerate all repository metadata for a Copr project
        """
        return self._common(copr)

    @api_login_required
    @editable_copr
    @apiv3_projects_ns.doc(params=fullname_params)
    @apiv3_projects_ns.marshal_with(project_model)
    @apiv3_projects_ns.response(
        HTTPStatus.OK.value, "OK, reposirory metadata regenerated"
    )
    @deprecated_route_method_type(apiv3_projects_ns, "POST", "PUT")
    def post(self, copr):
        """
        Regenerate all repository metadata for a Copr project
        """
        return self._common(copr)
