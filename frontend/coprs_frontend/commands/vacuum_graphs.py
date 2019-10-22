import click
import time
from sqlalchemy import and_, or_
from coprs import db
from coprs import models

@click.command()
def vacuum_graphs():
     """
     Removes old cached graph data that is no longer used.
     """
     curr_time = int(time.time())
     models.BuildsStatistics.query.filter(or_(
          and_(models.BuildsStatistics.time < curr_time - 91 * 86400,
               models.BuildsStatistics.stat_type == '24h'),
          and_(models.BuildsStatistics.time < curr_time - 87000,
               models.BuildsStatistics.stat_type == '30min'),
          and_(models.BuildsStatistics.time < curr_time - 87000,
               models.BuildsStatistics.stat_type == '10min')
     )).delete()
     db.session.commit()
