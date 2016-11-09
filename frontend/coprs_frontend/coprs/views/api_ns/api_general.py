import base64
import datetime
from functools import wraps
import json
import os
import flask

from werkzeug import secure_filename

from coprs import db
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models
from coprs.helpers import fix_protocol_for_backend, generate_build_config
from coprs.logic.api_logic import MonitorWrapper
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.users_logic import UsersLogic
from coprs.logic.packages_logic import PackagesLogic

from coprs.views.misc import login_required, api_login_required

from coprs.views.api_ns import api_ns

from coprs.logic import builds_logic
from coprs.logic import coprs_logic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.actions_logic import ActionsLogic

from coprs.exceptions import (ActionInProgressException,
                              InsufficientRightsException,
                              DuplicateException,
                              LegacyApiError,
                              UnknownSourceTypeException)


def api_req_with_copr(f):
    @wraps(f)
    def wrapper(username, coprname, **kwargs):
        if username.startswith("@"):
            group_name = username[1:]
            copr = ComplexLogic.get_group_copr_safe(group_name, coprname)
        else:
            copr = ComplexLogic.get_copr_safe(username, coprname)

        return f(copr, **kwargs)
    return wrapper


@api_ns.route("/")
def api_home():
    """
    Render the home page of the api.
    This page provides information on how to call/use the API.
    """

    return flask.render_template("api.html")


@api_ns.route("/new/", methods=["GET", "POST"])
@login_required
def api_new_token():
    """
    Generate a new API token for the current user.
    """

    user = flask.g.user
    copr64 = base64.b64encode(b"copr") + b"##"
    api_login = helpers.generate_api_token(
        flask.current_app.config["API_TOKEN_LENGTH"] - len(copr64))
    user.api_login = api_login
    user.api_token = helpers.generate_api_token(
        flask.current_app.config["API_TOKEN_LENGTH"])
    user.api_token_expiration = datetime.date.today() + \
        datetime.timedelta(
            days=flask.current_app.config["API_TOKEN_EXPIRATION"])

    db.session.add(user)
    db.session.commit()
    return flask.redirect(flask.url_for("api_ns.api_home"))


@api_ns.route("/coprs/<username>/new/", methods=["POST"])
@api_login_required
def api_new_copr(username):
    """
    Receive information from the user on how to create its new copr,
    check their validity and create the corresponding copr.

    :arg name: the name of the copr to add
    :arg chroots: a comma separated list of chroots to use
    :kwarg repos: a comma separated list of repository that this copr
        can use.
    :kwarg initial_pkgs: a comma separated list of initial packages to
        build in this new copr

    """

    form = forms.CoprFormFactory.create_form_cls()(csrf_enabled=False)
    infos = []

    # are there any arguments in POST which our form doesn't know?
    # TODO: don't use WTFform for parsing and validation here
    for post_key in flask.request.form.keys():
        if post_key not in form.__dict__.keys():
            infos.append("Unknown key '{key}' received.".format(key=post_key))

    if form.validate_on_submit():
        group = ComplexLogic.get_group_by_name_safe(username[1:]) if username[0] == "@" else None

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
            )
            infos.append("New project was successfully created.")

            if form.initial_pkgs.data:
                pkgs = form.initial_pkgs.data.split()
                for pkg in pkgs:
                    builds_logic.BuildsLogic.add(
                        user=flask.g.user,
                        pkgs=pkg,
                        copr=copr)

                infos.append("Initial packages were successfully "
                             "submitted for building.")

            output = {"output": "ok", "message": "\n".join(infos)}
            db.session.commit()
        except (exceptions.DuplicateException, exceptions.NonAdminCannotCreatePersistentProject) as err:
            db.session.rollback()
            raise LegacyApiError(str(err))

    else:
        errormsg = "Validation error\n"
        if form.errors:
            for field, emsgs in form.errors.items():
                errormsg += "- {0}: {1}\n".format(field, "\n".join(emsgs))

        errormsg = errormsg.replace('"', "'")
        raise LegacyApiError(errormsg)

    return flask.jsonify(output)


@api_ns.route("/coprs/<username>/<coprname>/delete/", methods=["POST"])
@api_login_required
@api_req_with_copr
def api_copr_delete(copr):
    """ Deletes selected user's project
    """
    form = forms.CoprDeleteForm(csrf_enabled=False)
    httpcode = 200

    if form.validate_on_submit() and copr:
        try:
            ComplexLogic.delete_copr(copr)
        except (exceptions.ActionInProgressException,
                exceptions.InsufficientRightsException) as err:

            db.session.rollback()
            raise LegacyApiError(str(err))
        else:
            message = "Project {} has been deleted.".format(copr.name)
            output = {"output": "ok", "message": message}
            db.session.commit()
    else:
        raise LegacyApiError("Invalid request: {0}".format(form.errors))

    return flask.jsonify(output)


@api_ns.route("/coprs/<username>/<coprname>/fork/", methods=["POST"])
@api_login_required
@api_req_with_copr
def api_copr_fork(copr):
    """ Fork the project and builds in it
    """
    form = forms.CoprForkFormFactory\
        .create_form_cls(copr=copr, user=flask.g.user, groups=flask.g.user.user_groups)(csrf_enabled=False)

    if form.validate_on_submit() and copr:
        try:
            dstgroup = ([g for g in flask.g.user.user_groups if g.at_name == form.owner.data] or [None])[0]
            if flask.g.user.name != form.owner.data and not dstgroup:
                return LegacyApiError("There is no such group: {}".format(form.owner.data))

            fcopr, created = ComplexLogic.fork_copr(copr, flask.g.user, dstname=form.name.data, dstgroup=dstgroup)
            if created:
                msg = ("Forking project {} for you into {}.\nPlease be aware that it may take a few minutes "
                       "to duplicate a backend data.".format(copr.full_name, fcopr.full_name))
            elif not created and form.confirm.data == True:
                msg = ("Updating packages in {} from {}.\nPlease be aware that it may take a few minutes "
                       "to duplicate a backend data.".format(copr.full_name, fcopr.full_name))
            else:
                raise LegacyApiError("You are about to fork into existing project: {}\n"
                                     "Please use --confirm if you really want to do this".format(fcopr.full_name))

            output = {"output": "ok", "message": msg}
            db.session.commit()

        except (exceptions.ActionInProgressException,
                exceptions.InsufficientRightsException) as err:
            db.session.rollback()
            raise LegacyApiError(str(err))
    else:
        raise LegacyApiError("Invalid request: {0}".format(form.errors))

    return flask.jsonify(output)


@api_ns.route("/coprs/")
@api_ns.route("/coprs/<username>/")
def api_coprs_by_owner(username=None):
    """ Return the list of coprs owned by the given user.
    username is taken either from GET params or from the URL itself
    (in this order).

    :arg username: the username of the person one would like to the
        coprs of.

    """
    username = flask.request.args.get("username", None) or username
    if username is None:
        raise LegacyApiError("Invalid request: missing `username` ")

    release_tmpl = "{chroot.os_release}-{chroot.os_version}-{chroot.arch}"

    if username.startswith("@"):
        group_name = username[1:]
        query = CoprsLogic.get_multiple()
        query = CoprsLogic.filter_by_group_name(query, group_name)
    else:
        query = CoprsLogic.get_multiple_owned_by_username(username)

    query = CoprsLogic.join_builds(query)
    query = CoprsLogic.set_query_order(query)

    repos = query.all()
    output = {"output": "ok", "repos": []}
    for repo in repos:
        yum_repos = {}
        for build in repo.builds:
            if build.results:
                for chroot in repo.active_chroots:
                    release = release_tmpl.format(chroot=chroot)
                    yum_repos[release] = fix_protocol_for_backend(
                        os.path.join(build.results, release + '/'))
                break

        output["repos"].append({"name": repo.name,
                                "additional_repos": repo.repos,
                                "yum_repos": yum_repos,
                                "description": repo.description,
                                "instructions": repo.instructions,
                                "persistent": repo.persistent,
                                "unlisted_on_hp": repo.unlisted_on_hp
                               })

    return flask.jsonify(output)


@api_ns.route("/coprs/<username>/<coprname>/detail/")
@api_req_with_copr
def api_coprs_by_owner_detail(copr):
    """ Return detail of one project.

    :arg username: the username of the person one would like to the
        coprs of.
    :arg coprname: the name of project.

    """
    release_tmpl = "{chroot.os_release}-{chroot.os_version}-{chroot.arch}"
    output = {"output": "ok", "detail": {}}
    yum_repos = {}

    build = models.Build.query.filter(models.Build.results != None).first()
    if build:
        for chroot in copr.active_chroots:
            release = release_tmpl.format(chroot=chroot)
            yum_repos[release] = fix_protocol_for_backend(
                os.path.join(build.results, release + '/'))

    output["detail"] = {
        "name": copr.name,
        "additional_repos": copr.repos,
        "yum_repos": yum_repos,
        "description": copr.description,
        "instructions": copr.instructions,
        "last_modified": builds_logic.BuildsLogic.last_modified(copr),
        "auto_createrepo": copr.auto_createrepo,
        "persistent": copr.persistent,
        "unlisted_on_hp": copr.unlisted_on_hp
    }
    return flask.jsonify(output)


@api_ns.route("/coprs/<username>/<coprname>/new_build/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build(copr):
    form = forms.BuildFormUrlFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        # create separate build for each package
        pkgs = form.pkgs.data.split("\n")
        return [BuildsLogic.create_new_from_url(
            flask.g.user, copr,
            srpm_url=pkg,
            chroot_names=form.selected_chroots,
            background=form.background.data,
        ) for pkg in pkgs]
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_upload/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_upload(copr):
    form = forms.BuildFormUploadFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_upload(
            flask.g.user, copr,
            f_uploader=lambda path: form.pkgs.data.save(path),
            orig_filename=secure_filename(form.pkgs.data.filename),
            chroot_names=form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_pypi/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_pypi(copr):
    form = forms.BuildFormPyPIFactory(copr.active_chroots)(csrf_enabled=False)

    # TODO: automatically prepopulate all form fields with their defaults
    if not form.python_versions.data:
        form.python_versions.data = form.python_versions.default

    def create_new_build():
        return BuildsLogic.create_new_from_pypi(
            flask.g.user,
            copr,
            form.pypi_package_name.data,
            form.pypi_package_version.data,
            form.python_versions.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_tito/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_tito(copr):
    form = forms.BuildFormTitoFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_tito(
            flask.g.user,
            copr,
            form.git_url.data,
            form.git_directory.data,
            form.git_branch.data,
            form.tito_test.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_mock/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_mock(copr):
    form = forms.BuildFormMockFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_mock(
            flask.g.user,
            copr,
            form.scm_type.data,
            form.scm_url.data,
            form.scm_branch.data,
            form.spec.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_rubygems/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_rubygems(copr):
    form = forms.BuildFormRubyGemsFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_rubygems(
            flask.g.user,
            copr,
            form.gem_name.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


@api_ns.route("/coprs/<username>/<coprname>/new_build_distgit/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_new_build_distgit(copr):
    form = forms.BuildFormDistGitFactory(copr.active_chroots)(csrf_enabled=False)

    def create_new_build():
        return BuildsLogic.create_new_from_distgit(
            flask.g.user,
            copr,
            form.clone_url.data,
            form.branch.data,
            form.selected_chroots,
            background=form.background.data,
        )
    return process_creating_new_build(copr, form, create_new_build)


def process_creating_new_build(copr, form, create_new_build):
    infos = []

    # are there any arguments in POST which our form doesn't know?
    for post_key in flask.request.form.keys():
        if post_key not in form.__dict__.keys():
            infos.append("Unknown key '{key}' received.".format(key=post_key))

    if not form.validate_on_submit():
        raise LegacyApiError("Invalid request: bad request parameters: {0}".format(form.errors))

    if not flask.g.user.can_build_in(copr):
        raise LegacyApiError("Invalid request: user {} is not allowed to build in the copr: {}"
                             .format(flask.g.user.username, copr.full_name))

    # create a new build
    try:
        # From URLs it can be created multiple builds at once
        # so it can return a list
        build = create_new_build()
        db.session.commit()
        ids = [build.id] if type(build) != list else [b.id for b in build]
        infos.append("Build was added to {0}.".format(copr.name))

    except (ActionInProgressException, InsufficientRightsException) as e:
        raise LegacyApiError("Invalid request: {}".format(e))

    output = {"output": "ok",
              "ids": ids,
              "message": "\n".join(infos)}

    return flask.jsonify(output)


@api_ns.route("/coprs/build_status/<int:build_id>/", methods=["GET"])
@api_login_required
def build_status(build_id):
    build = ComplexLogic.get_build_safe(build_id)
    output = {"output": "ok",
              "status": build.state}
    return flask.jsonify(output)


@api_ns.route("/coprs/build_detail/<int:build_id>/", methods=["GET"])
@api_ns.route("/coprs/build/<int:build_id>/", methods=["GET"])
def build_detail(build_id):
    build = ComplexLogic.get_build_safe(build_id)

    chroots = {}
    results_by_chroot = {}
    for chroot in build.build_chroots:
        chroots[chroot.name] = chroot.state
        results_by_chroot[chroot.name] = chroot.result_dir_url

    built_packages = None
    if build.built_packages:
        built_packages = build.built_packages.split("\n")

    output = {
        "output": "ok",
        "status": build.state,
        "project": build.copr.name,
        "owner": build.copr.owner_name,
        "results": build.results,
        "built_pkgs": built_packages,
        "src_version": build.pkg_version,
        "chroots": chroots,
        "submitted_on": build.submitted_on,
        "started_on": build.min_started_on,
        "ended_on": build.max_ended_on,
        "src_pkg": build.pkgs,
        "submitted_by": build.user.name,
        "results_by_chroot": results_by_chroot
    }
    return flask.jsonify(output)


@api_ns.route("/coprs/cancel_build/<int:build_id>/", methods=["POST"])
@api_login_required
def cancel_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)

    try:
        builds_logic.BuildsLogic.cancel_build(flask.g.user, build)
        db.session.commit()
    except exceptions.InsufficientRightsException as e:
        raise LegacyApiError("Invalid request: {}".format(e))

    output = {'output': 'ok', 'status': "Build canceled"}
    return flask.jsonify(output)


@api_ns.route("/coprs/delete_build/<int:build_id>/", methods=["POST"])
@api_login_required
def delete_build(build_id):
    build = ComplexLogic.get_build_safe(build_id)

    try:
        builds_logic.BuildsLogic.delete_build(flask.g.user, build)
        db.session.commit()
    except (exceptions.InsufficientRightsException,exceptions.ActionInProgressException) as e:
        raise LegacyApiError("Invalid request: {}".format(e))

    output = {'output': 'ok', 'status': "Build deleted"}
    return flask.jsonify(output)


@api_ns.route('/coprs/<username>/<coprname>/modify/', methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_modify(copr):
    form = forms.CoprModifyForm(csrf_enabled=False)

    if not form.validate_on_submit():
        raise LegacyApiError("Invalid request: {0}".format(form.errors))

    # .raw_data needs to be inspected to figure out whether the field
    # was not sent or was sent empty
    if form.description.raw_data and len(form.description.raw_data):
        copr.description = form.description.data
    if form.instructions.raw_data and len(form.instructions.raw_data):
        copr.instructions = form.instructions.data
    if form.repos.raw_data and len(form.repos.raw_data):
        copr.repos = form.repos.data
    if form.disable_createrepo.raw_data and len(form.disable_createrepo.raw_data):
        copr.disable_createrepo = form.disable_createrepo.data

    if "unlisted_on_hp" in flask.request.form != None:
        copr.unlisted_on_hp = form.unlisted_on_hp.data
    if "build_enable_net" in flask.request.form != None:
        copr.build_enable_net = form.build_enable_net.data

    try:
        CoprsLogic.update(flask.g.user, copr)
        if copr.group: # load group.id
            _ = copr.group.id
        db.session.commit()
    except (exceptions.ActionInProgressException, exceptions.InsufficientRightsException) as e:
        db.session.rollback()
        raise LegacyApiError("Invalid request: {}".format(e))

    output = {
        'output': 'ok',
        'description': copr.description,
        'instructions': copr.instructions,
        'repos': copr.repos,
    }

    return flask.jsonify(output)


@api_ns.route('/coprs/<username>/<coprname>/modify/<chrootname>/', methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_modify_chroot(copr, chrootname):
    form = forms.ModifyChrootForm(csrf_enabled=False)
    # chroot = coprs_logic.MockChrootsLogic.get_from_name(chrootname, active_only=True).first()
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)

    if not form.validate_on_submit():
        raise LegacyApiError("Invalid request: {0}".format(form.errors))
    else:
        coprs_logic.CoprChrootsLogic.update_chroot(flask.g.user, chroot, form.buildroot_pkgs.data)
        db.session.commit()

    output = {'output': 'ok', 'buildroot_pkgs': chroot.buildroot_pkgs}
    return flask.jsonify(output)


@api_ns.route('/coprs/<username>/<coprname>/detail/<chrootname>/', methods=["GET"])
@api_req_with_copr
def copr_chroot_details(copr, chrootname):
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chrootname)
    output = {'output': 'ok', 'buildroot_pkgs': chroot.buildroot_pkgs}
    return flask.jsonify(output)


@api_ns.route("/coprs/search/")
@api_ns.route("/coprs/search/<project>/")
def api_coprs_search_by_project(project=None):
    """ Return the list of coprs found in search by the given text.
    project is taken either from GET params or from the URL itself
    (in this order).

    :arg project: the text one would like find for coprs.

    """
    project = flask.request.args.get("project", None) or project
    if not project:
        raise LegacyApiError("No project found.")

    try:
        query = CoprsLogic.get_multiple_fulltext(project)

        repos = query.all()
        output = {"output": "ok", "repos": []}
        for repo in repos:
            output["repos"].append({"username": repo.user.name,
                                    "coprname": repo.name,
                                    "description": repo.description})
    except ValueError as e:
        raise LegacyApiError("Server error: {}".format(e))

    return flask.jsonify(output)


@api_ns.route("/playground/list/")
def playground_list():
    """ Return list of coprs which are part of playground """
    query = CoprsLogic.get_playground()
    repos = query.all()
    output = {"output": "ok", "repos": []}
    for repo in repos:
        output["repos"].append({"username": repo.owner_name,
                                "coprname": repo.name,
                                "chroots": [chroot.name for chroot in repo.active_chroots]})

    jsonout = flask.jsonify(output)
    jsonout.status_code = 200
    return jsonout


@api_ns.route("/coprs/<username>/<coprname>/monitor/", methods=["GET"])
@api_req_with_copr
def monitor(copr):
    monitor_data = builds_logic.BuildsMonitorLogic.get_monitor_data(copr)
    output = MonitorWrapper(copr, monitor_data).to_dict()
    return flask.jsonify(output)

###############################################################################

@api_ns.route("/coprs/<username>/<coprname>/package/add/<source_type_text>/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_add_package(copr, source_type_text):
    return process_package_add_or_edit(copr, source_type_text)


@api_ns.route("/coprs/<username>/<coprname>/package/<package_name>/edit/<source_type_text>/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_edit_package(copr, package_name, source_type_text):
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
    except IndexError:
        raise LegacyApiError("Package {name} does not exists in copr {copr}.".format(name=package_name, copr=copr.full_name))
    return process_package_add_or_edit(copr, source_type_text, package=package)


def process_package_add_or_edit(copr, source_type_text, package=None):
    try:
        form = forms.get_package_form_cls_by_source_type_text(source_type_text)(csrf_enabled=False)
    except UnknownSourceTypeException:
        raise LegacyApiError("Unsupported package source type {source_type_text}".format(source_type_text=source_type_text))

    if form.validate_on_submit():
        if not package:
            try:
                package = PackagesLogic.add(flask.app.g.user, copr, form.package_name.data)
            except InsufficientRightsException:
                raise LegacyApiError("Insufficient permissions.")
            except DuplicateException:
                raise LegacyApiError("Package {0} already exists in copr {1}.".format(form.package_name.data, copr.full_name))

        package.source_type = helpers.BuildSourceEnum(source_type_text)
        package.webhook_rebuild = form.webhook_rebuild.data
        package.source_json = form.source_json

        db.session.add(package)
        db.session.commit()
    else:
        raise LegacyApiError(form.errors)

    return flask.jsonify({
        "output": "ok",
        "message": "Create or edit operation was successful.",
        "package": package.to_dict(),
    })


def get_package_record_params():
    params = {}
    if flask.request.args.get('with_latest_build'):
        params['with_latest_build'] = True
    if flask.request.args.get('with_latest_succeeded_build'):
        params['with_latest_succeeded_build'] = True
    if flask.request.args.get('with_all_builds'):
        params['with_all_builds'] = True
    return params


def generate_package_list(query, params):
    """
    A lagging generator to stream JSON so we don't have to hold everything in memory
    This is a little tricky, as we need to omit the last comma to make valid JSON,
    thus we use a lagging generator, similar to http://stackoverflow.com/questions/1630320/
    """
    packages = query.__iter__()
    try:
        prev_package = next(packages)  # get first result
    except StopIteration:
        # StopIteration here means the length was zero, so yield a valid packages doc and stop
        yield '{"packages": []}'
        raise StopIteration
    # We have some packages. First, yield the opening json
    yield '{"packages": ['
    # Iterate over the packages
    for package in packages:
        yield json.dumps(prev_package.to_dict(**params)) + ', '
        prev_package = package
    # Now yield the last iteration without comma but with the closing brackets
    yield json.dumps(prev_package.to_dict(**params)) + ']}'


@api_ns.route("/coprs/<username>/<coprname>/package/list/", methods=["GET"])
@api_req_with_copr
def copr_list_packages(copr):
    packages = PackagesLogic.get_all(copr.id)
    params = get_package_record_params()
    return flask.Response(generate_package_list(packages, params), content_type='application/json')
    #return flask.jsonify({"packages": [package.to_dict(**params) for package in packages]})


@api_ns.route("/coprs/<username>/<coprname>/package/get/<package_name>/", methods=["GET"])
@api_req_with_copr
def copr_get_package(copr, package_name):
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
    except IndexError:
        raise LegacyApiError("No package with name {name} in copr {copr}".format(name=package_name, copr=copr.name))

    params = get_package_record_params()
    return flask.jsonify({'package': package.to_dict(**params)})


@api_ns.route("/coprs/<username>/<coprname>/package/delete/<package_name>/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_delete_package(copr, package_name):
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
    except IndexError:
        raise LegacyApiError("No package with name {name} in copr {copr}".format(name=package_name, copr=copr.name))

    try:
        PackagesLogic.delete_package(flask.g.user, package)
        db.session.commit()
    except (InsufficientRightsException, ActionInProgressException) as e:
        raise LegacyApiError(str(e))

    return flask.jsonify({
        "output": "ok",
        "message": "Package was successfully deleted.",
        'package': package.to_dict(),
    })


@api_ns.route("/coprs/<username>/<coprname>/package/reset/<package_name>/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_reset_package(copr, package_name):
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
    except IndexError:
        raise LegacyApiError("No package with name {name} in copr {copr}".format(name=package_name, copr=copr.name))

    try:
        PackagesLogic.reset_package(flask.g.user, package)
        db.session.commit()
    except InsufficientRightsException as e:
        raise LegacyApiError(str(e))

    return flask.jsonify({
        "output": "ok",
        "message": "Package's default source was successfully reseted.",
        'package': package.to_dict(),
    })


@api_ns.route("/coprs/<username>/<coprname>/package/build/<package_name>/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_build_package(copr, package_name):
    form = forms.BuildFormRebuildFactory.create_form_cls(copr.active_chroots)(csrf_enabled=False)

    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
    except IndexError:
        raise LegacyApiError("No package with name {name} in copr {copr}".format(name=package_name, copr=copr.name))

    if form.validate_on_submit():
        try:
            build = PackagesLogic.build_package(flask.g.user, copr, package, form.selected_chroots, **form.data)
            db.session.commit()
        except (InsufficientRightsException, ActionInProgressException, NoPackageSourceException) as e:
            raise LegacyApiError(str(e))
    else:
        raise LegacyApiError(form.errors)

    return flask.jsonify({
        "output": "ok",
        "ids": [build.id],
        "message": "Build was added to {0}.".format(copr.name)
    })


@api_ns.route("/coprs/<username>/<coprname>/module/build/", methods=["POST"])
@api_login_required
@api_req_with_copr
def copr_build_module(copr):
    form = forms.ModuleFormUploadFactory(csrf_enabled=False)
    if not form.validate_on_submit():
        # @TODO Prettier error
        raise LegacyApiError(form.errors)

    modulemd = form.modulemd.data.read()
    ActionsLogic.send_build_module(flask.g.user, copr, modulemd)
    db.session.commit()

    return flask.jsonify({
        "output": "ok",
        "message": "Module build was submitted",
        "modulemd": modulemd,
    })


@api_ns.route("/coprs/<username>/<coprname>/build-config/<chroot>/", methods=["GET"])
@api_ns.route("/g/<group_name>/<coprname>/build-config/<chroot>/", methods=["GET"])
@api_req_with_copr
def copr_build_config(copr, chroot):
    """
    Generate build configuration.
    """
    output = {
        "output": "ok",
        "build_config": generate_build_config(copr, chroot),
    }

    if not output['build_config']:
        raise LegacyApiError('Chroot not found.')

    return flask.jsonify(output)
