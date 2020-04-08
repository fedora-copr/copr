import click
from . import deprioritize_actions
from coprs import db_session_scope
from coprs.logic.complex_logic import ComplexLogic


@click.command()
@deprioritize_actions
def clean_expired_projects():
    """
    Clean all the expired temporary projects.  This command is meant to be
    executed by cron.
    """

    with db_session_scope():
        ComplexLogic.delete_expired_projects()
