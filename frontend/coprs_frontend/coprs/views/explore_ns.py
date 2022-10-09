import flask
from coprs import models
from coprs.logic.stat_logic import CounterStatLogic
from coprs.logic.coprs_logic import CoprScoreLogic, CoprsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic


explore_ns = flask.Blueprint("explore_ns", __name__, url_prefix="/explore")


@explore_ns.route("/")
def explore_home():
    stats_projects = CounterStatLogic.get_popular_projects()
    stats_chroots = CounterStatLogic.get_popular_chroots()

    upvoted_projects_ids = [x.copr_id for x in
                            CoprScoreLogic.get_popular_projects()]
    upvoted_projects = (CoprsLogic.get_multiple()
                        .filter(models.Copr.id.in_(upvoted_projects_ids)))

    return flask.render_template(
        "explore.html",
        stats_projects=stats_projects,
        stats_chroots=stats_chroots,
        upvoted_projects=upvoted_projects,

        # Meh this should be done automatically
        tasks_info=ComplexLogic.get_queue_sizes_cached(),
        graph=BuildsLogic.get_small_graph_data('30min'),
    )
