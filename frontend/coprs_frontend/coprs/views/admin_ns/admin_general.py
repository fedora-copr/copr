import time
import re

import flask
from sqlalchemy.exc import IntegrityError

from copr_common.enums import RoleEnum
from coprs import db
from coprs import models
from coprs import forms

from coprs.logic import coprs_logic
from coprs.logic.coprs_logic import ProjectTagsLogic

from coprs.views.admin_ns import admin_ns
from coprs.views.misc import login_required

from coprs.exceptions import InsufficientRightsException


@admin_ns.route("/")
@login_required(role=RoleEnum("admin"))
def admin_index():
    return flask.redirect(flask.url_for("admin_ns.legal_flag"))


@admin_ns.route("/legal-flag/")
@login_required(role=RoleEnum("admin"))
def legal_flag():
    legal_flags = (
        models.LegalFlag.query
        .outerjoin(models.LegalFlag.copr)
        .options(db.contains_eager(models.LegalFlag.copr))
        .filter(models.LegalFlag.resolved_on == None)
        .order_by(models.LegalFlag.raised_on.desc())
        .all())

    return flask.render_template("admin/legal-flag.html",
                                 legal_flags=legal_flags)


@admin_ns.route("/legal-flag/<int:flag_id>/resolve/", methods=["POST"])
@login_required(role=RoleEnum("admin"))
def legal_flag_resolve(flag_id):

    (models.LegalFlag.query
     .filter(models.LegalFlag.id == flag_id)
     .update({"resolved_on": int(time.time()),
              "resolver_id": flask.g.user.id}))

    db.session.commit()
    flask.flash("Legal flag resolved")
    return flask.redirect(flask.url_for("admin_ns.legal_flag"))


@admin_ns.route("/tags/")
@login_required(role=RoleEnum("admin"))
def tags():
    """
    List the default (admin-curated) project tags for management.
    """
    return flask.render_template("admin/tags.html",
                                 tags=ProjectTagsLogic.get_default_tags().all())


@admin_ns.route("/tags/create/", methods=["POST"])
@login_required(role=RoleEnum("admin"))
def tag_create():
    """
    Create (or reuse) one or more tags by name and mark them as default.
    """
    names = forms.ProjectTagsFilter()(flask.request.form.get("name", ""))
    if not names:
        flask.flash("Please provide at least one valid tag name.", "error")
    else:
        for name in names:
            tag = ProjectTagsLogic.create_tag(name, user=flask.g.user)
            tag.is_default = True
        db.session.commit()
        flask.flash("Created default tag(s): {0}".format(", ".join(names)))
    return flask.redirect(flask.url_for("admin_ns.tags"))


@admin_ns.route("/tags/<int:tag_id>/rename/", methods=["POST"])
@login_required(role=RoleEnum("admin"))
def tag_rename(tag_id):
    """
    Rename an existing tag
    """
    tag = models.ProjectTag.query.get_or_404(tag_id)
    new_name = forms.ProjectTagsFilter.normalize_tag_name(
        flask.request.form.get("name", ""))

    if not new_name or len(new_name) < 3:
        flask.flash("Please provide a valid tag name (at least 3 characters).", "error")
        return flask.redirect(flask.url_for("admin_ns.tags"))

    old_name = tag.name
    tag.name = new_name
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flask.flash(f"A tag named '{new_name}' already exists.", "error")
    else:
        flask.flash(f"Renamed tag '{old_name}' to '{new_name}'.")
    return flask.redirect(flask.url_for("admin_ns.tags"))


@admin_ns.route("/tags/<int:tag_id>/delete/", methods=["POST"])
@login_required(role=RoleEnum("admin"))
def tag_delete(tag_id):
    """
    Delete a tag, detaching it from every project that had it.
    """
    tag = models.ProjectTag.query.get_or_404(tag_id)
    name = tag.name
    ProjectTagsLogic.delete_tag(tag)
    db.session.commit()
    flask.flash(f"Deleted tag '{name}' and detached it from all projects.")
    return flask.redirect(flask.url_for("admin_ns.tags"))


@admin_ns.route("/playground/", methods=["POST", "GET"])
@login_required(role=RoleEnum("admin"))
def playground():
    form = forms.AdminPlaygroundSearchForm()

    if form.validate_on_submit() and form.project.data:
        m = re.match(r"(.+)/(.+)", form.project.data)
        if not m:
            flask.flash("Please search as username/projectname")
        else:
            username = m.group(1)
            coprname = m.group(2)

            copr = coprs_logic.CoprsLogic.get(username, coprname).first()

            if copr:
                return flask.redirect(flask.url_for(
                    "admin_ns.playground_project",
                    username=username,
                    coprname=coprname))
            else:
                flask.flash("This project does not exist")

    return flask.render_template("admin/playground.html", form_search=form)


@admin_ns.route("/playground/<username>/<coprname>/")
@login_required(role=RoleEnum("admin"))
def playground_project(username, coprname):
    copr = coprs_logic.CoprsLogic.get(username, coprname).first()
    if not copr:
        flask.flash("Project {0} does not exist".format(copr))
        return flask.render_template("admin/playground.html")

    form = forms.AdminPlaygroundForm()
    form.playground.data = copr.playground
    return flask.render_template("admin/playground.html", form_set=form, copr=copr)


@admin_ns.route("/playground/<username>/<coprname>/set/", methods=["POST"])
@login_required(role=RoleEnum("admin"))
def playground_set(username, coprname):
    copr = coprs_logic.CoprsLogic.get(username, coprname).first()
    if copr:
        form = forms.AdminPlaygroundForm()

        if form.validate_on_submit():
            try:
                copr.playground = form.playground.data
                coprs_logic.CoprsLogic.set_playground(flask.g.user, copr)
            except InsufficientRightsException as e:
                flask.flash(str(e))
                db.session.rollback()
            else:
                flask.flash("Playground flag has been updated")
                db.session.commit()

    return flask.redirect(flask.url_for("admin_ns.playground_project",
                                        username=username,
                                        coprname=coprname))
