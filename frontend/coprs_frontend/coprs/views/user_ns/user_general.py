import flask
from . import user_ns
from wtforms import ValidationError
from coprs.logic.users_logic import UsersLogic, UserDataDumper
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic


@user_ns.route("/<username>/info")
def user_info(username):
    if not flask.g.user or flask.g.user.name != username:
        raise ValidationError("You are not allowed to see personal information of another user.")

    user = UsersLogic.get(username).first()
    graph = BuildsLogic.get_running_tasks_from_last_day()
    return flask.render_template("user_info.html",
                                 user=user,
                                 tasks_info=ComplexLogic.get_queue_sizes(),
                                 graph=graph)


@user_ns.route("/<username>/info/download")
def user_info_download(username):
    if not flask.g.user or flask.g.user.name != username:
        raise ValidationError("You are not allowed to see personal information of another user.")

    user = UsersLogic.get(username).first()
    dumper = UserDataDumper(user)
    response = flask.make_response(dumper.dumps(pretty=True))
    response.mimetype = "application/json"
    response.headers["Content-Disposition"] = "attachment; filename={0}.json".format(user.name)
    return response


@user_ns.route("/<username>/delete")
def delete_data(username):
    if not flask.g.user or flask.g.user.name != username:
        raise ValidationError("You are not allowed to delete information of another user.")

    UsersLogic.delete_user_data(username)
    flask.flash("Your data were successfully deleted.")

    user = UsersLogic.get(username).first()
    graph = BuildsLogic.get_running_tasks_from_last_day()
    return flask.render_template("user_info.html",
                                 user=user,
                                 tasks_info=ComplexLogic.get_queue_sizes(),
                                 graph=graph)
