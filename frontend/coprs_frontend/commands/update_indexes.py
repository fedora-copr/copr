import click
import whoosh
from flask_whooshee import Whooshee
from coprs import app
from coprs.whoosheers import CoprWhoosheer, WhoosheeStamp
from coprs.logic import coprs_logic

@click.command()
def update_indexes():
    """
    recreates whoosh indexes for all projects
    """
    index = Whooshee.get_or_create_index(app, CoprWhoosheer)

    # Our index is huge, if necessary, tweak some performance options
    # https://whoosh.readthedocs.io/en/latest/batch.html
    writer = index.writer(procs=4, limitmb=128, multisegment=True)
    writer.schema = CoprWhoosheer.schema

    app.logger.info("Building cache")
    coprs = coprs_logic.CoprsLogic.get_multiple(
        include_unlisted_on_hp=False).all()
    for i, copr in enumerate(coprs):
        if i%1000 == 0:
            app.logger.info("Building cache [%s/%s] - %s",
                            i, len(coprs), copr.full_name)
        CoprWhoosheer.insert_copr(writer, copr)

    # Commit changes but don't merge them with the existing index.
    # Instead, build a new index from scratch.
    # https://whoosh.readthedocs.io/en/latest/indexing.html#id1
    app.logger.info("Running commit")
    writer.commit(mergetype=whoosh.writing.CLEAR)

    app.logger.info("Creating timestamp")
    WhoosheeStamp.store()
