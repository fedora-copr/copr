"""
Views for the per-project "Actions" tab.  Actions are background tasks
processed by backend (createrepo, fork, delete, ...) and when they fail, there
was historically no way to find out what happened.
"""

import flask

from coprs.exceptions import ObjectNotFound
from coprs.logic.actions_logic import ActionsLogic
from coprs.views.coprs_ns import coprs_ns
from coprs.views.misc import req_with_copr


@coprs_ns.route("/<username>/<coprname>/actions/")
@coprs_ns.route("/g/<group_name>/<coprname>/actions/")
@req_with_copr
def copr_actions(copr):
    """
    List all the actions in the project.  We intentionally don't do server-side
    pagination here (unlike e.g. the Builds tab) so the datatables filtering
    always works with the complete history.
    """
    actions = ActionsLogic.get_copr_actions(copr).yield_per(1000)
    return flask.render_template("coprs/detail/actions.html",
                                 copr=copr, actions=actions)


@coprs_ns.route("/<username>/<coprname>/action/<int:action_id>/")
@coprs_ns.route("/g/<group_name>/<coprname>/action/<int:action_id>/")
@req_with_copr
def copr_action(copr, action_id):
    """ Detail of a single action, including its raw data """
    action = ActionsLogic.get(action_id).first()
    if not action or action.copr_id != copr.id:
        raise ObjectNotFound(
            f"Action {action_id} not found in project {copr.full_name}.")
    return flask.render_template("coprs/detail/action.html",
                                 copr=copr, action=action)
