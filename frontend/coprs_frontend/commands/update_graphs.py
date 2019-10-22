import click
from coprs.logic import builds_logic


@click.command()
def update_graphs():
    """
    Generates newest graph data.
    """
    builds_logic.BuildsLogic.get_task_graph_data('10min')
    builds_logic.BuildsLogic.get_small_graph_data('30min')
    builds_logic.BuildsLogic.get_task_graph_data('24h')
