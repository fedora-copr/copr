# coding: utf-8

import flask
from flask import render_template, session
from coprs.forms import ActivateFasGroupForm
from coprs.helpers import Paginator
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.users_logic import UsersLogic

from coprs.views.misc import login_required

from . import groups_ns


@groups_ns.route("/activate/<fas_group>", methods=["GET", "POST"])
@login_required
def activate_group(fas_group):
    form = ActivateFasGroupForm()


    if False: #form.validate_on_submit():
        group = UsersLogic.get_group_by_fas_name_or_create(
            form.fas_name.data, form.name.data)

        # copr.group_id = group.id
        # db.session.add(copr)
        # db.session.commit()
        #
        # flask.flash(
        #     "Project is now managed by {} FAS group, "
        #     "main url to the project: {}"
        #     .format(
        #         form.fas_name.data,
        #         "group url todo:"
        #     )
        # )
        # return flask.redirect(flask.url_for(
        #     "coprs_ns.copr_detail", username=username, coprname=coprname))

    else:
        return flask.render_template(
            "groups/activate_fas_group.html",
            form=form, user=flask.g.user,
        )


@groups_ns.route("/by_user/<user_name>")
def list_groups_by_user(user_name):
    query = CoprsLogic.get_multiple()
    pass


@groups_ns.route("/g/<group_name>/coprs/", defaults={"page": 1})
@groups_ns.route("/g/<group_name>/coprs/<int:page>")
def list_projects_by_group(group_name, page=1):
    group = ComplexLogic.get_group_by_name_safe(group_name)
    query = CoprsLogic.get_multiple_by_group_id(group.id)

    paginator = Paginator(query, query.count(), page)

    coprs = paginator.sliced_query

    return render_template(
        "coprs/show/group.html",
        user=flask.g.user,
        coprs=coprs,
        paginator=paginator,
        tasks_info=ComplexLogic.get_queues_size(),
        group=group
    )


@groups_ns.route("/list/my")
@login_required
def list_user_groups():
    teams = session.get("teams")
    print(teams)
    active_map = {
        group.fas_name: group.name for group in
        UsersLogic.get_groups_by_fas_names_list(teams).all()
    }
    copr_groups = {
        fas_name: active_map.get(fas_name)
        for fas_name in teams
    }
    print(copr_groups)
    return render_template(
        "groups/user_fas_groups.html",
        user=flask.g.user,
        teams=teams,
        copr_groups=copr_groups)

