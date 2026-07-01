"""
List all owners that have projects in some storage
"""

from itertools import batched
import click
from copr_common.enums import StorageEnum
from coprs.logic.coprs_logic import CoprsLogic
from coprs import models


@click.command()
@click.option(
    "--storage",
    required=True,
    type=click.Choice(["backend", "pulp"]),
)
@click.option(
    "--prefix",
    required=False,
)
@click.option(
    "--chunks",
    required=False,
    type=click.IntRange(min=1),
)
@click.option(
    "--commas",
    is_flag=True,
)
def owners_in_storage(storage, prefix, chunks, commas):
    """
    List all owners that have projects in some storage
    """
    owners = set()
    projects = CoprsLogic.get_all().filter(
        models.Copr.storage == StorageEnum(storage)
    )
    for project in projects:
        if prefix and not project.owner_name.startswith(prefix):
            continue
        owners.add(project.owner_name)

    if not chunks:
        chunks = len(owners) + 1

    for chunk in batched(sorted(owners), chunks):
        for i, owner in enumerate(chunk):
            if commas and i != len(chunk) - 1:
                print(f"{owner},")
            else:
                print(owner)
        print("")
