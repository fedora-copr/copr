import flask
from coprs import app, db, models, helpers
from coprs.forms import PinnedCoprsForm
from coprs.views.misc import login_required
from coprs.logic.users_logic import UsersLogic, UserDataDumper
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import PinnedCoprsLogic
from coprs.logic.outdated_chroots_logic import OutdatedChrootsLogic
from coprs.views.coprs_ns.coprs_general import process_copr_repositories
from . import user_ns


def render_user_info(user):
    graph = BuildsLogic.get_small_graph_data('30min')
    return flask.render_template("user_info.html",
                                 user=user,
                                 tasks_info=ComplexLogic.get_queue_sizes_cached(),
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
    UsersLogic.delete_user_data(flask.g.user)
    db.session.commit()
    flask.flash("Your data were successfully deleted.")
    return render_user_info(flask.g.user)


@user_ns.route("/customize-pinned/")
@user_ns.route("/customize-pinned/<group_name>")
@login_required
def pinned_projects(group_name=None):
    owner = flask.g.user if not group_name else ComplexLogic.get_group_by_name_safe(group_name)
    return render_pinned_projects(owner)


def render_pinned_projects(owner, form=None):
    pinned = [pin.copr for pin in PinnedCoprsLogic.get_by_owner(owner)]
    coprs = ComplexLogic.get_coprs_pinnable_by_owner(owner)
    selected = [copr.id for copr in pinned]
    selected += (app.config["PINNED_PROJECTS_LIMIT"] - len(pinned)) * [None]
    for i, copr_id in enumerate(form.copr_ids.data if form else []):
        selected[i] = int(copr_id) if copr_id else None

    graph = BuildsLogic.get_small_graph_data('30min')
    return flask.render_template("pinned.html",
                                 owner=owner,
                                 pinned=pinned,
                                 selected=selected,
                                 coprs=coprs,
                                 form=form,
                                 tasks_info=ComplexLogic.get_queue_sizes_cached(),
                                 graph=graph)


@user_ns.route("/customize-pinned/", methods=["POST"])
@user_ns.route("/customize-pinned/<group_name>", methods=["POST"])
@login_required
def pinned_projects_post(group_name=None):
    owner = flask.g.user if not group_name else ComplexLogic.get_group_by_name_safe(group_name)
    url_on_success = helpers.owner_url(owner)
    return process_pinned_projects_post(owner, url_on_success)


def process_pinned_projects_post(owner, url_on_success):
    if isinstance(owner, models.Group):
        UsersLogic.raise_if_not_in_group(flask.g.user, owner)

    form = PinnedCoprsForm(owner)
    if not form.validate_on_submit():
        return render_pinned_projects(owner, form=form)

    PinnedCoprsLogic.delete_by_owner(owner)
    for i, copr_id in enumerate(filter(None, form.copr_ids.data)):
        PinnedCoprsLogic.add(owner, int(copr_id), i)
    db.session.commit()

    return flask.redirect(url_on_success)


@user_ns.route("/repositories/")
@login_required
def repositories():
    return render_repositories()


def render_repositories(*_args, **_kwargs):
    owner = flask.g.user
    projects = ComplexLogic.get_coprs_permissible_by_user(owner)
    projects = sorted(projects, key=lambda p: p.full_name)
    OutdatedChrootsLogic.make_review(owner)
    db.session.commit()
    return flask.render_template("repositories.html",
                                 tasks_info=ComplexLogic.get_queue_sizes_cached(),
                                 graph=BuildsLogic.get_small_graph_data('30min'),
                                 owner=owner,
                                 projects=projects)


@user_ns.route("/repositories/", methods=["POST"])
@login_required
def repositories_post():
    return process_copr_repositories(copr=None, on_success=render_repositories)
