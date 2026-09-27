import click
import time
from sqlalchemy import and_, or_
from coprs import db
from coprs import models

# How long we keep cached graph data around, per stat_type.  Anything older
# gets pruned.  The '24h' series is used by the 90-days graph, the rest only by
# the 24-hours graph.
STAT_TYPE_RETENTION = {
    '24h': 91 * 86400,
    '30min': 87000,
    '10min': 87000,
}


def _vacuum_statistics(model):
    """
    Remove obsolete rows from a *Statistics model (BuildsStatistics,
    ActionsStatistics, ...).  The model only needs to have the 'time' and
    'stat_type' columns.
    """
    curr_time = int(time.time())
    conditions = [
        and_(model.time < curr_time - retention, model.stat_type == stat_type)
        for stat_type, retention in STAT_TYPE_RETENTION.items()
    ]
    model.query.filter(or_(*conditions)).delete()


@click.command()
def vacuum_graphs():
    """
    Removes old cached graph data that is no longer used.
    """
    _vacuum_statistics(models.BuildsStatistics)
    _vacuum_statistics(models.ActionsStatistics)
    db.session.commit()
