import click
from coprs.logic import actions_logic, builds_logic


@click.command()
def update_graphs():
    """
    Generates newest graph data.
    """
    builds_logic.BuildsLogic.get_task_graph_data('10min')
    builds_logic.BuildsLogic.get_small_graph_data('30min')
    builds_logic.BuildsLogic.get_task_graph_data('24h')
    actions_logic.ActionsLogic.get_action_graph_data('10min')
    actions_logic.ActionsLogic.get_action_graph_data('24h')
