from flask_script import Command, Option
from coprs import db
from coprs.logic import builds_logic
from commands.create_sqlite_file import CreateSqliteFileCommand


class CreateDBCommand(Command):

    """
    Create the DB schema
    """

    def run(self, alembic_ini=None):
        CreateSqliteFileCommand().run()
        db.create_all()

        # load the Alembic configuration and generate the
        # version table, "stamping" it with the most recent rev:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

        # Functions are not covered by models.py, and no migrations are run
        # by command.stamp() above.  Create functions explicitly:
        builds_logic.BuildsLogic.init_db()

    option_list = (
        Option("--alembic",
               "-f",
               dest="alembic_ini",
               help="Path to the alembic configuration file (alembic.ini)",
               required=True),
    )
