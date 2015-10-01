# coding: utf-8

import flask
from flask import render_template, session
from coprs.logic.users_logic import UsersLogic

from coprs.views.misc import login_required

from . import groups_ns


@groups_ns.route("/activate/<fas_group>", methods=["GET", "POST"])
@login_required
def activate_group(fas_group):
    pass


@groups_ns.route("/by_user/<user_name>")
def list_groups_by_user(user_name):
    pass


@groups_ns.route("/g/<group_name>/coprs")
def list_projects_by_group(group_name):
    pass


@groups_ns.route("/add/")
@login_required
def add():
    teams = session.get("teams")
    copr_groups = {fas_group : UsersLogic.get_group_by_fas_name(fas_group) for fas_group in teams}
    return render_template("coprs/add_group.html",
                                 username=flask.g.user.name,
                                 teams=teams, copr_groups=copr_groups)
