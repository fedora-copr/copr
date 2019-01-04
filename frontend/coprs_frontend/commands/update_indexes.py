from flask_script import Command
from flask_whooshee import Whooshee
from coprs import app
from coprs.whoosheers import CoprWhoosheer
from coprs.logic import coprs_logic


class UpdateIndexesCommand(Command):
    """
    recreates whoosh indexes for all projects
    """

    def run(self):
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
