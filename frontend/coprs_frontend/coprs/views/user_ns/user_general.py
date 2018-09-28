import flask
from . import user_ns
from coprs.views.misc import login_required
from coprs.logic.users_logic import UsersLogic, UserDataDumper
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic


def render_user_info(user):
    graph = BuildsLogic.get_small_graph_data('30min')
    return flask.render_template("user_info.html",
                                 user=user,
                                 tasks_info=ComplexLogic.get_queue_sizes(),
                                 graph=graph)


@user_ns.route("/info")
@login_required
def user_info():
    return render_user_info(flask.g.user)


@user_ns.route("/info/download")
@login_required
def user_info_download():
    user = flask.g.user
    dumper = UserDataDumper(user)
    response = flask.make_response(dumper.dumps(pretty=True))
    response.mimetype = "application/json"
    response.headers["Content-Disposition"] = "attachment; filename={0}.json".format(user.name)
    return response


@user_ns.route("/delete")
@login_required
def delete_data():
    UsersLogic.delete_user_data(flask.g.user.username)
    flask.flash("Your data were successfully deleted.")
    return render_user_info(flask.g.user)
