import os
import flask
import click
from coprs import app


def create_sqlite_file_function():
    uri = app.config["SQLALCHEMY_DATABASE_URI"]

    if not uri.startswith("sqlite"):
        return None

    # strip sqlite:///
    datadir_name = os.path.dirname(uri[10:])
    if not os.path.exists(datadir_name):
        os.makedirs(datadir_name)

@click.command()
def create_sqlite_file():
    """
    Create the sqlite DB file (not the tables).
    Used for alembic, "create-db" does this automatically.
    """
    return create_sqlite_file()
