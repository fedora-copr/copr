import click
from coprs.logic import coprs_logic


@click.command()
@click.option(
    "--active-only/--all", "active_only",
    help="Display only active chroots.",
    default=True
)
def display_chroots(active_only):
    """Displays current mock chroots"""
    for ch in coprs_logic.MockChrootsLogic.get_multiple(
            active_only=active_only).all():

        print(ch.name)
