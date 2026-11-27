"""
List all projects that are hosted in a given storage
"""

import click
from copr_common.enums import StorageEnum
from coprs.logic.coprs_logic import CoprsLogic
from coprs import models


@click.command()
@click.option(
    "--storage",
    default="pulp",
    type=click.Choice(["backend", "pulp"]),
    help="List projects that are hosted in this storage",
)
def projects_in_storage(storage):
    """
    List all projects that are hosted in a given storage
    """
    query = CoprsLogic.get_all().filter(
        models.Copr.storage == StorageEnum(storage)
    )
    for copr in sorted(query, key=lambda c: c.full_name):
        print(copr.full_name)
