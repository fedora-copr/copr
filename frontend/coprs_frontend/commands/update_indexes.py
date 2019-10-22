import click
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

    writer = index.writer()
    for copr in coprs_logic.CoprsLogic.get_all():
        CoprWhoosheer.delete_copr(writer, copr)
    writer.commit(optimize=True)

    writer = index.writer()
    writer.schema = CoprWhoosheer.schema
    writer.commit(optimize=True)

    writer = index.writer()
    for copr in coprs_logic.CoprsLogic.get_all():
        CoprWhoosheer.insert_copr(writer, copr)
    writer.commit(optimize=True)

    WhoosheeStamp.store()
