import flask
from coprs.logic.users_logic import UsersLogic
from coprs.views.misc import login_required
from coprs.views.coprs_ns import coprs_ns

@coprs_ns.route("/group/add/")
@login_required
def group_add():
    teams = flask.session.get("teams")
    copr_groups = {fas_group : UsersLogic.get_group_by_fas_name(fas_group) for fas_group in teams}
    return flask.render_template("coprs/add_group.html",
                                 username=flask.g.user.name,
                                 teams=teams, copr_groups=copr_groups)
