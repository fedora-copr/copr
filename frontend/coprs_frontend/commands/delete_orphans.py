import click
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.packages_logic import PackagesLogic


@click.command()
def delete_orphans():
    """
    Deletes builds and packages associated to deleted coprs.
    """
    BuildsLogic.delete_orphaned_builds()
    PackagesLogic.delete_orphaned_packages()
