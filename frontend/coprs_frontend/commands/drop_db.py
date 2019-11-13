from coprs import db
import click


@click.command()
def drop_db():
    """
    Delete DB
    """
    db.drop_all()
