from flask_script import Command
from coprs.logic import builds_logic


class UpdateGraphsDataCommand(Command):
    """
    Generates newest graph data.
    """

    def run(self):
        builds_logic.BuildsLogic.get_task_graph_data('10min')
        builds_logic.BuildsLogic.get_small_graph_data('30min')
        builds_logic.BuildsLogic.get_task_graph_data('24h')
