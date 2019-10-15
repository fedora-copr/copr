from coprs import db
import click


"""
Delete DB
"""

@click.command()
def drop_db():
    db.drop_all()
