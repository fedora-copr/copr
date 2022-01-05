"""
command: copr-frontend create-db (./manage.py create-db)
"""

from alembic.config import Config
from alembic import command
import click

from coprs import db
from commands.create_sqlite_file import create_sqlite_file_function


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
    db.session.commit()
    # load the Alembic configuration and generate the
    # version table, "stamping" it with the most recent rev:
    alembic_cfg = Config(alembic_ini)
    command.stamp(alembic_cfg, "head")
