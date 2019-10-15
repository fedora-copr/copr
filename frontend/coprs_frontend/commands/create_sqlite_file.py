import os
import flask
import click


"""
Create the sqlite DB file (not the tables).
Used for alembic, "create_db" does this automatically.
"""

def create_sqlite_file():
    if flask.current_app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        # strip sqlite:///
        datadir_name = os.path.dirname(
            flask.current_app.config["SQLALCHEMY_DATABASE_URI"][10:])
        if not os.path.exists(datadir_name):
            os.makedirs(datadir_name)

@click.command()
def create_sqlite_file_command():
    return create_sqlite_file()
