import flask
import re

from coprs import db
from coprs import forms
from coprs import helpers

from coprs.logic import builds_logic
from coprs.logic import coprs_logic

from coprs.views.misc import login_required, page_not_found
from coprs.views.coprs_ns import coprs_ns

from coprs.exceptions import (ActionInProgressException,
                              InsufficientRightsException)



@coprs_ns.route("/build/<int:build_id>/")
def copr_build_redirect(build_id):
    build = builds_logic.BuildsLogic.get_by_id(build_id)
    if not build:
        return page_not_found(
            "Build {0} does not exist.".format(str(build_id)))

    return flask.redirect(flask.url_for("coprs_ns.copr_build",
                                        username=build.copr.owner.name,
                                        coprname=build.copr.name,
                                        build_id=build_id))


@coprs_ns.route("/<username>/<coprname>/build/<int:build_id>/")
def copr_build(username, coprname, build_id):
    build = builds_logic.BuildsLogic.get_by_id(build_id)
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not build:
        return page_not_found(
            "Build {0} does not exist.".format(str(build_id)))

    if not copr: # but the build does
        return flask.render_template("coprs/detail/build-no-project.html",
                                        build=build,
                                        username=username,
                                        coprname=coprname)

    return flask.render_template("coprs/detail/build.html",
                                        build=build,
                                        copr=copr)


@coprs_ns.route("/<username>/<coprname>/builds/", defaults={"page": 1})
@coprs_ns.route("/<username>/<coprname>/builds/<int:page>/")
def copr_builds(username, coprname, page=1):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not copr:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    builds_query = builds_logic.BuildsLogic.get_multiple(
        flask.g.user, copr=copr)

    paginator = helpers.Paginator(
        builds_query, copr.build_count, page, per_page_override=30)

    return flask.render_template("coprs/detail/builds.html",
                                 copr=copr,
                                 builds=paginator.sliced_query,
                                 paginator=paginator)


@coprs_ns.route("/<username>/<coprname>/add_build/")
@login_required
def copr_add_build(username, coprname, form=None):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()

    if not copr:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    if not form:
        form = forms.BuildFormFactory.create_form_cls(copr.active_chroots)()

    return flask.render_template("coprs/detail/add_build.html",
                                 copr=copr,
                                 form=form)


@coprs_ns.route("/<username>/<coprname>/new_build/", methods=["POST"])
@login_required
def copr_new_build(username, coprname):
    copr = coprs_logic.CoprsLogic.get(flask.g.user, username, coprname).first()
    if not copr:
        return page_not_found(
            "Copr with name {0} does not exist.".format(coprname))

    form = forms.BuildFormFactory.create_form_cls(copr.active_chroots)()

    if form.validate_on_submit():
        pkgs = form.pkgs.data.replace("\n", " ").split(" ")

        # validate (and skip bad) urls
        bad_urls = []
        for pkg in pkgs:
            if not re.match("^.*\.src\.rpm$", pkg):
                bad_urls.append(pkg)
                flask.flash("Bad url: {0} (skipped)".format(pkg))
        for bad_url in bad_urls:
            pkgs.remove(bad_url)

        if not pkgs:
            flask.flash("No builds submitted")
        else:
            # check which chroots we need
            chroots = []
            for chroot in copr.active_chroots:
                if chroot.name in form.selected_chroots:
                    chroots.append(chroot)

            # build each package as a separate build
            try:
                for pkg in pkgs:
                    build = builds_logic.BuildsLogic.add(
                        user=flask.g.user,
                        pkgs=pkg,
                        copr=copr,
                        chroots=chroots)

                    if flask.g.user.proven:
                        build.memory_reqs = form.memory_reqs.data
                        build.timeout = form.timeout.data

            except (ActionInProgressException, InsufficientRightsException) as e:
                flask.flash(str(e))
                db.session.rollback()
            else:
                flask.flash("Build was added")
                db.session.commit()

        return flask.redirect(flask.url_for("coprs_ns.copr_builds",
                                            username=username,
                                            coprname=copr.name))
    else:
        return copr_add_build(username=username, coprname=coprname, form=form)


@coprs_ns.route("/<username>/<coprname>/cancel_build/<int:build_id>/",
                defaults={"page": 1},
                methods=["POST"])
@coprs_ns.route("/<username>/<coprname>/cancel_build/<int:build_id>/<int:page>/",
                methods=["POST"])
@login_required
def copr_cancel_build(username, coprname, build_id, page=1):
    # only the user who ran the build can cancel it
    build = builds_logic.BuildsLogic.get(build_id).first()
    if not build:
        return page_not_found(
            "Build with id {0} does not exist.".format(build_id))
    try:
        builds_logic.BuildsLogic.cancel_build(flask.g.user, build)
    except InsufficientRightsException as e:
        flask.flash(str(e))
    else:
        db.session.commit()
        flask.flash("Build was canceled")

    return flask.redirect(flask.url_for("coprs_ns.copr_builds",
                                        username=username,
                                        coprname=coprname,
                                        page=page))


@coprs_ns.route("/<username>/<coprname>/repeat_build/<int:build_id>/",
                defaults={"page": 1},
                methods=["GET", "POST"])
@coprs_ns.route("/<username>/<coprname>/repeat_build/<int:build_id>/<int:page>/",
                methods=["GET", "POST"])
@login_required
def copr_repeat_build(username, coprname, build_id, page=1):
    build = builds_logic.BuildsLogic.get(build_id).first()
    copr = coprs_logic.CoprsLogic.get(
        flask.g.user, username=username, coprname=coprname).first()

    if not build:
        return page_not_found(
            "Build with id {0} does not exist.".format(build_id))

    if not copr:
        return page_not_found(
            "Copr {0}/{1} does not exist.".format(username, coprname))

    try:
        builds_logic.BuildsLogic.add(
            user=flask.g.user,
            pkgs=build.pkgs,
            copr=copr,
            repos=build.repos,
            memory_reqs=build.memory_reqs,
            timeout=build.timeout)

    except (ActionInProgressException, InsufficientRightsException) as e:
        db.session.rollback()
        flask.flash(str(e))
    else:
        db.session.commit()
        flask.flash("Build was resubmitted")

    return flask.redirect(flask.url_for("coprs_ns.copr_builds",
                                        username=username,
                                        coprname=coprname,
                                        page=page))


@coprs_ns.route("/<username>/<coprname>/delete_build/<int:build_id>/",
                defaults={"page": 1},
                methods=["POST"])
@coprs_ns.route("/<username>/<coprname>/delete_build/<int:build_id>/<int:page>/",
                methods=["POST"])
@login_required
def copr_delete_build(username, coprname, build_id, page=1):
    build = builds_logic.BuildsLogic.get(build_id).first()
    if not build:
        return page_not_found(
            "Build with id {0} does not exist.".format(build_id))
    try:
        builds_logic.BuildsLogic.delete_build(flask.g.user, build)
    except (InsufficientRightsException, ActionInProgressException) as e:
        flask.flash(str(e))
    else:
        db.session.commit()
        flask.flash("Build was deleted")

    return flask.redirect(flask.url_for("coprs_ns.copr_builds",
                                        username=username, coprname=coprname,
                                        page=page))
