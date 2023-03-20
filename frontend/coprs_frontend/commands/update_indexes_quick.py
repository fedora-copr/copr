import time
import click
from flask_whooshee import Whooshee
from coprs import db
from coprs import app
from coprs import models
from coprs.whoosheers import CoprWhoosheer


@click.command()
@click.argument("minutes_passed", type=int)
def update_indexes_quick(minutes_passed):
    """
    Recreates whoosh indexes for projects for which
    indexed data were updated in last n minutes.
    Doesn't update schema.
    """
    index = Whooshee.get_or_create_index(app, CoprWhoosheer)

    writer = index.writer()
    query = db.session.query(models.Copr).filter(
        models.Copr.latest_indexed_data_update >= time.time()-int(minutes_passed)*60
    )

    coprs = query.all()
    app.logger.info("Updating %s projects", len(coprs))
    for copr in coprs:
        CoprWhoosheer.delete_copr(writer, copr)
        CoprWhoosheer.insert_copr(writer, copr)
    writer.commit(optimize=True)
