from coprs import db
from coprs.logic import builds_logic
from commands.create_sqlite_file import create_sqlite_file_function
import click


@click.command()
@click.option(
    "--alembic", "-f", "alembic_ini",
    help="Path to the alembic configuration file (alembic.ini)",
    required=True
)
def create_db(alembic_ini):
    """
    Create the DB schema
    """
    create_sqlite_file_function()
    db.create_all()
    # load the Alembic configuration and generate the
    # version table, "stamping" it with the most recent rev:
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config(alembic_ini)
    command.stamp(alembic_cfg, "head")
