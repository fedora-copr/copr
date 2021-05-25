"""
Admin/Cron logic for removing outdated CoprDir objects
"""

import click

from coprs import db
from coprs.logic.coprs_logic import CoprDirsLogic

def _delete_dirs_function():
    CoprDirsLogic.send_delete_dirs_action()
    db.session.commit()

@click.command()
def delete_dirs():
    """
    Delete outdated pull request directories (e.g. like copr-dev:pr:123)
    from the database and generate an action so the data are removed from
    backend, too.
    """
    _delete_dirs_function()
