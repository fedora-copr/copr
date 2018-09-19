# coding: utf-8

import os
import time
import fnmatch
import uuid
import subprocess
import json

from six.moves.urllib.parse import urljoin

import flask
from flask import render_template, url_for, stream_with_context
import platform
import smtplib
import tempfile
import sqlalchemy
from email.mime.text import MIMEText
from itertools import groupby
from wtforms import ValidationError

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

from copr_common.enums import StatusEnum
from coprs import app
from coprs import db
from coprs import rcp
from coprs import exceptions
from coprs import forms
from coprs import helpers
from coprs import models
from coprs.exceptions import ObjectNotFound
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.stat_logic import CounterStatLogic
from coprs.logic.modules_logic import ModulesLogic, ModulemdGenerator, ModuleBuildFacade
from coprs.rmodels import TimedStatEvents
from coprs.mail import send_mail, LegalFlagMessage, PermissionRequestMessage, PermissionChangeMessage

from coprs.logic.complex_logic import ComplexLogic

from coprs.views.misc import login_required, page_not_found, req_with_copr, req_with_copr, generic_error

from coprs.views.coprs_ns import coprs_ns
from coprs.views.groups_ns import groups_ns

from coprs.logic import builds_logic, coprs_logic, actions_logic, users_logic
from coprs.helpers import parse_package_name, generate_repo_url, CHROOT_RPMS_DL_STAT_FMT, CHROOT_REPO_MD_DL_STAT_FMT, \
    str2bool, url_for_copr_view, REPO_DL_STAT_FMT, CounterStatType

def url_for_copr_details(copr):
    return url_for_copr_view(
        "coprs_ns.copr_detail",
        "coprs_ns.copr_detail",
        copr)


def url_for_copr_edit(copr):
    return url_for_copr_view(
        "coprs_ns.copr_edit",
        "coprs_ns.copr_edit",
        copr)


@coprs_ns.route("/", defaults={"page": 1})
@coprs_ns.route("/<int:page>/")
def coprs_show(page=1):
    query = CoprsLogic.get_multiple(include_unlisted_on_hp=False)
    query = CoprsLogic.set_query_order(query, desc=True)

    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query

    # flask.g.user is none when no user is logged - showing builds from everyone
    # TODO: builds_logic.BuildsLogic.get_recent_tasks(flask.g.user, 5) takes too much time, optimize sql
    # users_builds = builds_logic.BuildsLogic.get_recent_tasks(flask.g.user, 5)
    users_builds = builds_logic.BuildsLogic.get_recent_tasks(None, 4)

    data = builds_logic.BuildsLogic.get_running_tasks_from_last_day()

    return flask.render_template("coprs/show/all.html",
                                 coprs=coprs,
                                 paginator=paginator,
                                 tasks_info=ComplexLogic.get_queue_sizes(),
                                 users_builds=users_builds,
                                 graph=data)


@coprs_ns.route("/<username>/", defaults={"page": 1})
@coprs_ns.route("/<username>/<int:page>/")
def coprs_by_user(username=None, page=1):
    user = users_logic.UsersLogic.get(username).first()
    if not user:
        return page_not_found(
            "User {0} does not exist.".format(username))

    query = CoprsLogic.get_multiple_owned_by_username(username)
    query = CoprsLogic.filter_without_group_projects(query)
    query = CoprsLogic.set_query_order(query, desc=True)

    paginator = helpers.Paginator(query, query.count(), page)

    coprs = paginator.sliced_query

    # flask.g.user is none when no user is logged - showing builds from everyone
    users_builds = builds_logic.BuildsLogic.get_recent_tasks(flask.g.user, 4)

    data = builds_logic.BuildsLogic.get_running_tasks_from_last_day()

    return flask.render_template("coprs/show/user.html",
                                 user=user,
                                 coprs=coprs,
                                 paginator=paginator,
                                 tasks_info=ComplexLogic.get_queue_sizes(),
                                 users_builds=users_builds,
                                 graph=data)


@coprs_ns.route("/fulltext/", defaults={"page": 1})
@coprs_ns.route("/fulltext/<int:page>/")
def coprs_fulltext_search(page=1):
    fulltext = flask.request.args.get("fulltext", "")
    try:
        query = coprs_logic.CoprsLogic.get_multiple_fulltext(fulltext)
    except ValueError as e:
        flask.flash(str(e), "error")
        return flask.redirect(flask.request.referrer or
                              flask.url_for("coprs_ns.coprs_show"))

    paginator = helpers.Paginator(query, query.count(), page,
                                  additional_params={"fulltext": fulltext})

    data = builds_logic.BuildsLogic.get_running_tasks_from_last_day()

    coprs = paginator.sliced_query
    return render_template("coprs/show/fulltext.html",
                            coprs=coprs,
                            paginator=paginator,
                            fulltext=fulltext,
                            tasks_info=ComplexLogic.get_queue_sizes(),
                            graph=data)


@coprs_ns.route("/<username>/add/")
@coprs_ns.route("/g/<group_name>/add/")
@login_required
def copr_add(username=None, group_name=None):
    form = forms.CoprFormFactory.create_form_cls()()
    if group_name:
        group = ComplexLogic.get_group_by_name_safe(group_name)
        return flask.render_template("coprs/group_add.html", form=form, group=group)
    return flask.render_template("coprs/add.html", form=form)


@coprs_ns.route("/<username>/new/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/new/", methods=["POST"])
@login_required
def copr_new(username=None, group_name=None):
    if group_name:
        return process_group_copr_new(group_name)
    return process_copr_new(username)


def process_group_copr_new(group_name):
    group = ComplexLogic.get_group_by_name_safe(group_name)
    form = forms.CoprFormFactory.create_form_cls(group=group)()

    if form.validate_on_submit():
        try:
            copr = coprs_logic.CoprsLogic.add(
                flask.g.user,
                name=form.name.data,
                homepage=form.homepage.data,
                contact=form.contact.data,
                repos=form.repos.data.replace("\n", " "),
                selected_chroots=form.selected_chroots,
                description=form.description.data,
                instructions=form.instructions.data,
                disable_createrepo=form.disable_createrepo.data,
                build_enable_net=form.build_enable_net.data,
                unlisted_on_hp=form.unlisted_on_hp.data,
                group=group,
                persistent=form.persistent.data,
                auto_prune=(form.auto_prune.data if flask.g.user.admin else True),
                use_bootstrap_container=form.use_bootstrap_container.data,
                follow_fedora_branching=form.follow_fedora_branching.data,
            )
        except (exceptions.DuplicateException, exceptions.NonAdminCannotCreatePersistentProject) as e:
            flask.flash(str(e), "error")
            return flask.render_template("coprs/group_add.html", form=form, group=group)

        db.session.add(copr)
        db.session.commit()
        after_the_project_creation(copr, form)

        return flask.redirect(url_for_copr_details(copr))
    else:
        return flask.render_template("coprs/group_add.html", form=form, group=group)


def process_copr_new(username):
    """
    Receive information from the user on how to create its new copr
    and create it accordingly.
    """

    form = forms.CoprFormFactory.create_form_cls()()
    if form.validate_on_submit():
        try:
            copr = coprs_logic.CoprsLogic.add(
                flask.g.user,
                name=form.name.data,
                homepage=form.homepage.data,
                contact=form.contact.data,
                repos=form.repos.data.replace("\n", " "),
                selected_chroots=form.selected_chroots,
                description=form.description.data,
                instructions=form.instructions.data,
                disable_createrepo=form.disable_createrepo.data,
                build_enable_net=form.build_enable_net.data,
                unlisted_on_hp=form.unlisted_on_hp.data,
                persistent=form.persistent.data,
                auto_prune=(form.auto_prune.data if flask.g.user.admin else True),
                use_bootstrap_container=form.use_bootstrap_container.data,
                follow_fedora_branching=form.follow_fedora_branching.data,
            )
        except (exceptions.DuplicateException, exceptions.NonAdminCannotCreatePersistentProject) as e:
            flask.flash(str(e), "error")
            return flask.render_template("coprs/add.html", form=form)

        db.session.commit()
        after_the_project_creation(copr, form)

        return flask.redirect(url_for_copr_details(copr))
    else:
        return flask.render_template("coprs/add.html", form=form)


def after_the_project_creation(copr, form):
    flask.flash("New project has been created successfully.", "success")
    _check_rpmfusion(copr.repos)
    if form.initial_pkgs.data:
        pkgs = form.initial_pkgs.data.replace("\n", " ").split(" ")

        # validate (and skip bad) urls
        bad_urls = []
        for pkg in pkgs:
            if not pkg.endswith(".src.rpm"):
                bad_urls.append(pkg)
                flask.flash("Bad url: {0} (skipped)".format(pkg))
        for bad_url in bad_urls:
            pkgs.remove(bad_url)

        if not pkgs:
            flask.flash("No initial packages submitted")
        else:
            # build each package as a separate build
            for pkg in pkgs:
                builds_logic.BuildsLogic.add(
                    flask.g.user,
                    pkgs=pkg,
                    srpm_url=pkg,
                    copr=copr,
                    enable_net=form.build_enable_net.data
                )

            db.session.commit()
            flask.flash("Initial packages were successfully submitted "
                        "for building.")


@coprs_ns.route("/<username>/<coprname>/report-abuse")
@coprs_ns.route("/g/<group_name>/<coprname>/report-abuse")
@req_with_copr
@login_required
def copr_report_abuse(copr):
    return render_copr_report_abuse(copr)


def render_copr_report_abuse(copr):
    form = forms.CoprLegalFlagForm()
    return render_template("coprs/report_abuse.html", copr=copr, form=form)


@coprs_ns.route("/<username>/<coprname>/")
@coprs_ns.route("/g/<group_name>/<coprname>/")
@req_with_copr
def copr_detail(copr):
    return render_copr_detail(copr)


def render_copr_detail(copr):
    repo_dl_stat = CounterStatLogic.get_copr_repo_dl_stat(copr)
    form = forms.CoprLegalFlagForm()
    repos_info = {}
    for chroot in copr.active_chroots:
        # chroot_rpms_dl_stat_key = CHROOT_REPO_MD_DL_STAT_FMT.format(
        #     copr_user=copr.user.name,
        #     copr_project_name=copr.name,
        #     copr_chroot=chroot.name,
        # )
        chroot_rpms_dl_stat_key = CHROOT_RPMS_DL_STAT_FMT.format(
            copr_user=copr.owner_name,
            copr_project_name=copr.name,
            copr_chroot=chroot.name,
        )
        chroot_rpms_dl_stat = TimedStatEvents.get_count(
            rconnect=rcp.get_connection(),
            name=chroot_rpms_dl_stat_key,
        )

        logoset = set()
        logodir = app.static_folder + "/chroot_logodir"
        for logo in os.listdir(logodir):
            # glob.glob() uses listdir() and fnmatch anyways
            if fnmatch.fnmatch(logo, "*.png"):
                logoset.add(logo[:-4])

        if chroot.name_release not in repos_info:
            logo = None
            if chroot.name_release in logoset:
                logo = chroot.name_release + ".png"
            elif chroot.os_release in logoset:
                logo = chroot.os_release + ".png"

            repos_info[chroot.name_release] = {
                "name_release": chroot.name_release,
                "os_release": chroot.os_release,
                "os_version": chroot.os_version,
                "logo": logo,
                "arch_list": [chroot.arch],
                "repo_file": "{}-{}.repo".format(copr.repo_id, chroot.name_release),
                "dl_stat": repo_dl_stat[chroot.name_release],
                "rpm_dl_stat": {
                    chroot.arch: chroot_rpms_dl_stat
                }
            }
        else:
            repos_info[chroot.name_release]["arch_list"].append(chroot.arch)
            repos_info[chroot.name_release]["rpm_dl_stat"][chroot.arch] = chroot_rpms_dl_stat
    repos_info_list = sorted(repos_info.values(), key=lambda rec: rec["name_release"])
    builds = builds_logic.BuildsLogic.get_multiple_by_copr(copr=copr).limit(1).all()

    return flask.render_template(
        "coprs/detail/overview.html",
        copr=copr,
        user=flask.g.user,
        form=form,
        repo_dl_stat=repo_dl_stat,
        repos_info_list=repos_info_list,
        latest_build=builds[0] if len(builds) == 1 else None,
    )


@coprs_ns.route("/<username>/<coprname>/permissions/")
@req_with_copr
def copr_permissions(copr):
    permissions = coprs_logic.CoprPermissionsLogic.get_for_copr(copr).all()
    if flask.g.user:
        user_perm = flask.g.user.permissions_for_copr(copr)
    else:
        user_perm = None

    permissions_applier_form = None
    permissions_form = None

    # generate a proper form for displaying
    if flask.g.user:
        # https://github.com/ajford/flask-wtf/issues/58
        permissions_applier_form = \
            forms.PermissionsApplierFormFactory.create_form_cls(
                user_perm)(formdata=None)

        if flask.g.user.can_edit(copr):
            permissions_form = forms.PermissionsFormFactory.create_form_cls(
                permissions)()

    return flask.render_template(
        "coprs/detail/settings/permissions.html",
        copr=copr,
        permissions_form=permissions_form,
        permissions_applier_form=permissions_applier_form,
        permissions=permissions,
        current_user_permissions=user_perm)


def render_copr_integrations(copr, pagure_form):
    if not copr.webhook_secret:
        copr.new_webhook_secret()
        db.session.add(copr)
        db.session.commit()

    bitbucket_url = "https://{}/webhooks/bitbucket/{}/{}/".format(
                     app.config["PUBLIC_COPR_HOSTNAME"],
                     copr.id,
                     copr.webhook_secret)

    github_url = "https://{}/webhooks/github/{}/{}/".format(
                  app.config["PUBLIC_COPR_HOSTNAME"],
                  copr.id,
                  copr.webhook_secret)

    gitlab_url = "https://{}/webhooks/gitlab/{}/{}/".format(
                  app.config["PUBLIC_COPR_HOSTNAME"],
                  copr.id,
                  copr.webhook_secret)

    custom_url = "https://{}/webhooks/custom/{}/{}/".format(
                  app.config["PUBLIC_COPR_HOSTNAME"],
                  copr.id,
                  copr.webhook_secret) + "<PACKAGE_NAME>/"

    return flask.render_template(
        "coprs/detail/settings/integrations.html",
        copr=copr, bitbucket_url=bitbucket_url, github_url=github_url,
        gitlab_url=gitlab_url, custom_url=custom_url, pagure_form=pagure_form)


@coprs_ns.route("/<username>/<coprname>/integrations/")
@coprs_ns.route("/g/<group_name>/<coprname>/integrations/")
@login_required
@req_with_copr
def copr_integrations(copr):
    if not flask.g.user.can_edit(copr):
        flask.flash("You don't have access to this page.", "error")
        return flask.redirect(url_for_copr_details(copr))

    if copr.scm_api_type == 'pagure':
        pagure_api_key = copr.scm_api_auth.get('api_key', '')
    else:
        pagure_api_key = ''

    pagure_form = forms.PagureIntegrationForm(
        api_key=pagure_api_key, repo_url=copr.scm_repo_url)
    return render_copr_integrations(copr, pagure_form)


@coprs_ns.route("/<username>/<coprname>/integrations/update", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/integrations/update", methods=["POST"])
@login_required
@req_with_copr
def copr_integrations_update(copr):
    if not flask.g.user.can_edit(copr):
        flask.flash("Access denied.", "error")
        return flask.redirect(url_for_copr_details(copr))

    pagure_form = forms.PagureIntegrationForm()

    if pagure_form.validate_on_submit():
        copr.scm_repo_url = pagure_form.repo_url.data
        copr.scm_api_type = 'pagure'
        copr.scm_api_auth_json = json.dumps({'api_key': pagure_form.api_key.data})
        db.session.add(copr)
        db.session.commit()
        flask.flash("Integrations have been updated.", 'success')
        return flask.redirect(helpers.copr_url("coprs_ns.copr_integrations", copr))
    else:
        return render_copr_integrations(copr, pagure_form)


def render_copr_edit(copr, form, view):
    if not form:
        form = forms.CoprFormFactory.create_form_cls(
            copr.mock_chroots)(obj=copr)
    return flask.render_template(
        "coprs/detail/settings/edit.html",
        copr=copr, form=form, view=view)


@coprs_ns.route("/<username>/<coprname>/edit/")
@coprs_ns.route("/g/<group_name>/<coprname>/edit/")
@login_required
@req_with_copr
def copr_edit(copr, form=None):
    return render_copr_edit(copr, form, 'coprs_ns.copr_update')


def _check_rpmfusion(repos):
    if "rpmfusion" in repos:
        message = flask.Markup('Using rpmfusion as dependency is nearly always wrong. Please see <a href="https://docs.pagure.org/copr.copr/user_documentation.html#what-i-can-build-in-copr">What I can build in Copr</a>.')
        flask.flash(message, "error")


def process_copr_update(copr, form):
    copr.name = form.name.data
    copr.homepage = form.homepage.data
    copr.contact = form.contact.data
    copr.repos = form.repos.data.replace("\n", " ")
    copr.description = form.description.data
    copr.instructions = form.instructions.data
    copr.disable_createrepo = form.disable_createrepo.data
    copr.build_enable_net = form.build_enable_net.data
    copr.unlisted_on_hp = form.unlisted_on_hp.data
    copr.use_bootstrap_container = form.use_bootstrap_container.data
    copr.follow_fedora_branching = form.follow_fedora_branching.data
    if flask.g.user.admin:
        copr.auto_prune = form.auto_prune.data
    else:
        copr.auto_prune = True
    coprs_logic.CoprChrootsLogic.update_from_names(
        flask.g.user, copr, form.selected_chroots)
    try:
        # form validation checks for duplicates
        coprs_logic.CoprsLogic.update(flask.g.user, copr)
    except (exceptions.ActionInProgressException,
            exceptions.InsufficientRightsException) as e:

        flask.flash(str(e), "error")
        db.session.rollback()
    else:
        flask.flash("Project has been updated successfully.", "success")
        db.session.commit()
    _check_rpmfusion(copr.repos)


@coprs_ns.route("/<username>/<coprname>/update/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/update/", methods=["POST"])
@login_required
@req_with_copr
def copr_update(copr):
    form = forms.CoprFormFactory.create_form_cls(user=copr.user, group=copr.group)()

    if form.validate_on_submit():
        process_copr_update(copr, form)
        return flask.redirect(url_for_copr_details(copr))
    else:
        return render_copr_edit(copr, form, 'coprs_ns.copr_update')


@coprs_ns.route("/<username>/<coprname>/permissions_applier_change/",
                methods=["POST"])
@login_required
@req_with_copr
def copr_permissions_applier_change(copr):
    permission = coprs_logic.CoprPermissionsLogic.get(copr, flask.g.user).first()
    applier_permissions_form = \
        forms.PermissionsApplierFormFactory.create_form_cls(permission)()

    if copr.user == flask.g.user:
        flask.flash("Owner cannot request permissions for his own project.", "error")
    elif applier_permissions_form.validate_on_submit():
        # we rely on these to be 0 or 1 from form. TODO: abstract from that
        if permission is not None:
            old_builder = permission.copr_builder
            old_admin = permission.copr_admin
        else:
            old_builder = 0
            old_admin = 0
        new_builder = applier_permissions_form.copr_builder.data
        new_admin = applier_permissions_form.copr_admin.data
        coprs_logic.CoprPermissionsLogic.update_permissions_by_applier(
            flask.g.user, copr, permission, new_builder, new_admin)
        db.session.commit()
        flask.flash(
            "Successfully updated permissions for project '{0}'."
            .format(copr.name))
        admin_mails = [copr.user.mail]
        for perm in copr.copr_permissions:
            # this 2 means that his status (admin) is approved
            if perm.copr_admin == 2:
                admin_mails.append(perm.user.mail)

        # sending emails
        if flask.current_app.config.get("SEND_EMAILS", False):
            for mail in admin_mails:
                permission_dict = {"old_builder": old_builder, "old_admin": old_admin,
                                   "new_builder": new_builder, "new_admin": new_admin}
                msg = PermissionRequestMessage(copr, flask.g.user, permission_dict)
                send_mail(mail, msg, )

    return flask.redirect(flask.url_for("coprs_ns.copr_detail",
                                        username=copr.user.name,
                                        coprname=copr.name))


@coprs_ns.route("/<username>/<coprname>/update_permissions/", methods=["POST"])
@login_required
@req_with_copr
def copr_update_permissions(copr):
    permissions = copr.copr_permissions
    permissions_form = forms.PermissionsFormFactory.create_form_cls(
        permissions)()

    if permissions_form.validate_on_submit():
        # we don't change owner (yet)
        try:
            # if admin is changing his permissions, his must be changed last
            # so that we don't get InsufficientRightsException
            permissions.sort(
                key=lambda x: -1 if x.user_id == flask.g.user.id else 1)
            for perm in permissions:
                old_builder = perm.copr_builder
                old_admin = perm.copr_admin
                new_builder = permissions_form[
                    "copr_builder_{0}".format(perm.user_id)].data
                new_admin = permissions_form[
                    "copr_admin_{0}".format(perm.user_id)].data
                coprs_logic.CoprPermissionsLogic.update_permissions(
                    flask.g.user, copr, perm, new_builder, new_admin)
                if flask.current_app.config.get("SEND_EMAILS", False) and \
                        (old_builder is not new_builder or old_admin is not new_admin):
                    permission_dict = {"old_builder": old_builder, "old_admin": old_admin,
                                       "new_builder": new_builder, "new_admin": new_admin}
                    msg = PermissionChangeMessage(copr, permission_dict)
                    send_mail(perm.user.mail, msg)
        # for now, we don't check for actions here, as permissions operation
        # don't collide with any actions
        except exceptions.InsufficientRightsException as e:
            db.session.rollback()
            flask.flash(str(e), "error")
        else:
            db.session.commit()
            flask.flash("Project permissions were updated successfully.", "success")

    return flask.redirect(url_for_copr_details(copr))


@coprs_ns.route("/id/<copr_id>/createrepo/", methods=["POST"])
@login_required
def copr_createrepo(copr_id):
    copr = ComplexLogic.get_copr_by_id_safe(copr_id)
    if not flask.g.user.can_edit(copr):
        flask.flash(
            "You are not allowed to recreate repository metadata of copr with id {}.".format(copr_id), "error")
        return flask.redirect(url_for_copr_details(copr))

    actions_logic.ActionsLogic.send_createrepo(copr)
    db.session.commit()

    flask.flash("Repository metadata in all directories will be regenerated...", "success")
    return flask.redirect(url_for_copr_details(copr))


def process_delete(copr, url_on_error, url_on_success):
    form = forms.CoprDeleteForm()
    if form.validate_on_submit():

        try:
            ComplexLogic.delete_copr(copr)
        except (exceptions.ActionInProgressException,
                exceptions.InsufficientRightsException) as e:

            db.session.rollback()
            flask.flash(str(e), "error")
            return flask.redirect(url_on_error)
        else:
            db.session.commit()
            flask.flash("Project has been deleted successfully.")
            return flask.redirect(url_on_success)
    else:
        return render_template("coprs/detail/settings/delete.html", form=form, copr=copr)


@coprs_ns.route("/<username>/<coprname>/delete/", methods=["GET", "POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/delete/", methods=["GET", "POST"])
@login_required
@req_with_copr
def copr_delete(copr):
    if copr.group:
        url_on_success = url_for("groups_ns.list_projects_by_group", group_name=copr.group.name)
    else:
        url_on_success = url_for("coprs_ns.coprs_by_user", username=copr.user.username)
    url_on_error = helpers.copr_url("coprs_ns.copr_detail", copr)
    return process_delete(copr, url_on_error, url_on_success)


@coprs_ns.route("/<username>/<coprname>/legal_flag/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/legal_flag/", methods=["POST"])
@login_required
@req_with_copr
def copr_legal_flag(copr):
    return process_legal_flag(copr)


def process_legal_flag(copr):
    form = forms.CoprLegalFlagForm()
    legal_flag = models.LegalFlag(raise_message=form.comment.data,
                                  raised_on=int(time.time()),
                                  copr=copr,
                                  reporter=flask.g.user)
    db.session.add(legal_flag)
    db.session.commit()

    send_to = app.config["SEND_LEGAL_TO"] or ["root@localhost"]
    msg = LegalFlagMessage(copr, flask.g.user, form.comment.data)
    send_mail(send_to, msg)

    flask.flash("Admin has been noticed about your report"
                " and will investigate the project shortly.")
    return flask.redirect(url_for_copr_details(copr))


@coprs_ns.route("/<username>/<copr_dirname>/repo/<name_release>/", defaults={"repofile": None})
@coprs_ns.route("/<username>/<copr_dirname>/repo/<name_release>/<repofile>")
@coprs_ns.route("/g/<group_name>/<copr_dirname>/repo/<name_release>/", defaults={"repofile": None})
@coprs_ns.route("/g/<group_name>/<copr_dirname>/repo/<name_release>/<repofile>")
def generate_repo_file(copr_dirname, name_release, repofile, username=None, group_name=None):
    """ Generate repo file for a given repo name.
        Reponame = username-coprname """

    ownername = username if username else ('@'+group_name)
    copr_dir = ComplexLogic.get_copr_dir_safe(ownername, copr_dirname)
    return render_generate_repo_file(copr_dir, name_release)


def render_generate_repo_file(copr_dir, name_release):
    mock_chroot = coprs_logic.MockChrootsLogic.get_from_name(name_release, noarch=True).first()

    if not mock_chroot:
        raise ObjectNotFound("Chroot {} does not exist".format(name_release))

    url = os.path.join(copr_dir.repo_url, '') # adds trailing slash
    repo_url = generate_repo_url(mock_chroot, url)
    pubkey_url = urljoin(url, "pubkey.gpg")
    response = flask.make_response(
        flask.render_template("coprs/copr_dir.repo", copr_dir=copr_dir, url=repo_url, pubkey_url=pubkey_url))
    response.mimetype = "text/plain"
    response.headers["Content-Disposition"] = \
        "filename={0}.repo".format(copr_dir.repo_name)

    name = REPO_DL_STAT_FMT.format(**{
        'copr_user': copr_dir.copr.user.name,
        'copr_project_name': copr_dir.copr.name,
        'copr_name_release': name_release,
    })
    CounterStatLogic.incr(name=name, counter_type=CounterStatType.REPO_DL)
    db.session.commit()

    return response


#########################################################
###                Module repo files                  ###
#########################################################

@coprs_ns.route("/<username>/<coprname>/module_repo/<name_release>/<module_nsv>.repo")
@coprs_ns.route("/g/<group_name>/<coprname>/module_repo/<name_release>/<module_nsv>.repo")
@req_with_copr
def generate_module_repo_file(copr, name_release, module_nsv):
    """ Generate module repo file for a given project. """
    return render_generate_module_repo_file(copr, name_release, module_nsv)

def render_generate_module_repo_file(copr, name_release, module_nsv):
    module = ModulesLogic.get_by_nsv_str(copr, module_nsv).one()
    mock_chroot = coprs_logic.MockChrootsLogic.get_from_name(name_release, noarch=True).first()
    url = os.path.join(copr_dir.repo_url, '') # adds trailing slash
    repo_url = generate_repo_url(mock_chroot, copr.modules_url)
    baseurl = "{}+{}/latest/$basearch".format(repo_url.rstrip("/"), module_nsv)
    pubkey_url = urljoin(url, "pubkey.gpg")
    response = flask.make_response(
        flask.render_template("coprs/copr-modules.cfg", copr=copr, module=module,
                              baseurl=baseurl, pubkey_url=pubkey_url))
    response.mimetype = "text/plain"
    response.headers["Content-Disposition"] = \
        "filename={0}.cfg".format(copr.repo_name)
    return response

#########################################################

@coprs_ns.route("/<username>/<coprname>/rpm/<name_release>/<rpmfile>")
def copr_repo_rpm_file(username, coprname, name_release, rpmfile):
    try:
        packages_dir = os.path.join(app.config["DATA_DIR"], "repo-rpm-packages")
        with open(os.path.join(packages_dir, rpmfile), "rb") as rpm:
            response = flask.make_response(rpm.read())
            response.mimetype = "application/x-rpm"
            response.headers["Content-Disposition"] = \
                "filename={0}".format(rpmfile)
            return response
    except IOError:
        return flask.render_template("404.html")


def render_monitor(copr, detailed=False):
    monitor = builds_logic.BuildsMonitorLogic.get_monitor_data(copr)
    oses = [chroot.os for chroot in copr.active_chroots_sorted]
    oses_grouped = [(len(list(group)), key) for key, group in groupby(oses)]
    archs = [chroot.arch for chroot in copr.active_chroots_sorted]
    if detailed:
        template = "coprs/detail/monitor/detailed.html"
    else:
        template = "coprs/detail/monitor/simple.html"
    return flask.Response(stream_with_context(helpers.stream_template(template,
                                 copr=copr,
                                 monitor=monitor,
                                 oses=oses_grouped,
                                 archs=archs,
                                 status_enum_func=StatusEnum)))


@coprs_ns.route("/<username>/<coprname>/monitor/")
@coprs_ns.route("/<username>/<coprname>/monitor/<detailed>")
@coprs_ns.route("/g/<group_name>/<coprname>/monitor/")
@coprs_ns.route("/g/<group_name>/<coprname>/monitor/<detailed>")
@req_with_copr
def copr_build_monitor(copr, detailed=False):
    return render_monitor(copr, detailed == "detailed")


@coprs_ns.route("/<username>/<coprname>/fork/")
@coprs_ns.route("/g/<group_name>/<coprname>/fork/")
@login_required
@req_with_copr
def copr_fork(copr):
    form = forms.CoprForkFormFactory.create_form_cls(copr=copr, user=flask.g.user, groups=flask.g.user.user_groups)()
    return render_copr_fork(copr, form)


def render_copr_fork(copr, form, confirm=False):
    return flask.render_template("coprs/fork.html", copr=copr, form=form, confirm=confirm)


@coprs_ns.route("/<username>/<coprname>/fork/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/fork/", methods=["POST"])
@login_required
@req_with_copr
def copr_fork_post(copr):
    form = forms.CoprForkFormFactory.create_form_cls(copr=copr, user=flask.g.user, groups=flask.g.user.user_groups)()
    if form.validate_on_submit():
        dstgroup = ([g for g in flask.g.user.user_groups if g.at_name == form.owner.data] or [None])[0]
        if flask.g.user.name != form.owner.data and not dstgroup:
            return generic_error("There is no such group: {}".format(form.owner.data))

        fcopr, created = ComplexLogic.fork_copr(copr, flask.g.user, dstname=form.name.data, dstgroup=dstgroup)
        if created:
            msg = ("Forking project {} for you into {}. Please be aware that it may take a few minutes "
                   "to duplicate backend data.".format(copr.full_name, fcopr.full_name))
        elif not created and form.confirm.data == True:
            msg = ("Updating packages in {} from {}. Please be aware that it may take a few minutes "
                   "to duplicate backend data.".format(copr.full_name, fcopr.full_name))
        else:
            return render_copr_fork(copr, form, confirm=True)

        db.session.commit()
        flask.flash(msg)

        return flask.redirect(url_for_copr_details(fcopr))
    return render_copr_fork(copr, form)


@coprs_ns.route("/update_search_index/", methods=["POST"])
def copr_update_search_index():
    subprocess.call(['/usr/share/copr/coprs_frontend/manage.py', 'update_indexes_quick', '1'])
    return "OK"


@coprs_ns.route("/<username>/<coprname>/modules/")
@coprs_ns.route("/g/<group_name>/<coprname>/modules/")
@req_with_copr
def copr_modules(copr):
    return render_copr_modules(copr)


def render_copr_modules(copr):
    modules = ModulesLogic.get_multiple_by_copr(copr=copr).all()
    return flask.render_template("coprs/detail/modules.html", copr=copr, modules=modules)


@coprs_ns.route("/<username>/<coprname>/create_module/")
@coprs_ns.route("/g/<group_name>/<coprname>/create_module/")
@login_required
@req_with_copr
def copr_create_module(copr):
    form = forms.CreateModuleForm()
    return render_create_module(copr, form)


def render_create_module(copr, form, profiles=2):
    built_packages = []
    for build in filter(None, [p.last_build(successful=True) for p in copr.packages]):
        for package in build.built_packages.split("\n"):
            built_packages.append((package.split()[0], build))

    return flask.render_template("coprs/create_module.html", copr=copr, form=form, built_packages=built_packages, profiles=profiles)


@coprs_ns.route("/<username>/<coprname>/create_module/", methods=["POST"])
@coprs_ns.route("/g/<group_name>/<coprname>/create_module/", methods=["POST"])
@login_required
@req_with_copr
def copr_create_module_post(copr):
    form = forms.CreateModuleForm(copr=copr, csrf_enabled=False)
    args = [copr, form]
    if "add_profile" in flask.request.values:
        return add_profile(*args)
    if "build_module" in flask.request.values:
        return build_module(*args)
    # @TODO Error


def add_profile(copr, form):
    n = len(form.profile_names) + 1
    form.profile_names.append_entry()
    for i in range(2, n):
        form.profile_pkgs.append_entry()
    return render_create_module(copr, form, profiles=n)


def build_module(copr, form):
    if not form.validate_on_submit():
        # WORKAROUND append those which are not in min_entries
        for i in range(2, len(form.profile_names)):
            form.profile_pkgs.append_entry()
        return render_create_module(copr, form, profiles=len(form.profile_names))

    summary = "Module from Copr repository: {}".format(copr.full_name)
    generator = ModulemdGenerator(str(copr.name), summary=summary, config=app.config)
    generator.add_filter(form.filter.data)
    generator.add_api(form.api.data)
    generator.add_profiles(enumerate(zip(form.profile_names.data, form.profile_pkgs.data)))
    generator.add_components(form.packages.data, form.filter.data, form.builds.data)
    yaml = generator.generate()

    facade = None
    try:
        facade = ModuleBuildFacade(flask.g.user, copr, yaml)
        module = facade.submit_build()
        db.session.commit()

        flask.flash("Modulemd yaml file successfully generated and submitted to be build as {}"
                    .format(module.nsv), "success")
        return flask.redirect(url_for_copr_details(copr))

    except ValidationError as ex:
        flask.flash(ex.message, "error")
        return render_create_module(copr, form, len(form.profile_names))

    except sqlalchemy.exc.IntegrityError:
        flask.flash("Module {}-{}-{} already exists".format(
            facade.modulemd.name, facade.modulemd.stream, facade.modulemd.version), "error")
        db.session.rollback()
        return render_create_module(copr, form, len(form.profile_names))


@coprs_ns.route("/<username>/<coprname>/module/<id>")
@coprs_ns.route("/g/<group_name>/<coprname>/module/<id>")
@req_with_copr
def copr_module(copr, id):
    module = ModulesLogic.get(id).first()
    formatter = HtmlFormatter(style="autumn", linenos=False, noclasses=True)
    pretty_yaml = highlight(module.yaml, get_lexer_by_name("YAML"), formatter)

    # Get the list of chroots with unique name_release attribute
    # Once we use jinja in 2.10 version, we can simply use
    # {{ copr.active_chroots |unique(attribute='name_release') }}
    unique_chroots = []
    unique_name_releases = set()
    for chroot in copr.active_chroots_sorted:
        if chroot.name_release in unique_name_releases:
            continue
        unique_chroots.append(chroot)
        unique_name_releases.add(chroot.name_release)

    return flask.render_template("coprs/detail/module.html", copr=copr, module=module,
                                 yaml=pretty_yaml, unique_chroots=unique_chroots)


@coprs_ns.route("/<username>/<coprname>/module/<id>/raw")
@coprs_ns.route("/g/<group_name>/<coprname>/module/<id>/raw")
@req_with_copr
def copr_module_raw(copr, id):
    module = ModulesLogic.get(id).first()
    response = flask.make_response(module.yaml)
    response.mimetype = "text/plain"
    response.headers["Content-Disposition"] = \
        "filename={}.yaml".format("-".join([str(module.id), module.name, module.stream, str(module.version)]))
    return response
