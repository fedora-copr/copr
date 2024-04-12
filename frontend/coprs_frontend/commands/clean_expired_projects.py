import click
from coprs import db
from . import deprioritize_actions
from coprs.logic.complex_logic import ComplexLogic


@click.command()
@deprioritize_actions
def clean_expired_projects():
    """
    Clean all the expired temporary projects.  This command is meant to be
    executed by cron.
    """
    while ComplexLogic.delete_expired_projects(limit=10):
        db.session.commit()
