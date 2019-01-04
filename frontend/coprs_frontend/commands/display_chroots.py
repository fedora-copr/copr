from flask_script import Command, Option
from coprs.logic import coprs_logic


class DisplayChrootsCommand(Command):

    "Displays current mock chroots"

    def run(self, active_only):
        for ch in coprs_logic.MockChrootsLogic.get_multiple(
                active_only=active_only).all():

            print(ch.name)

    option_list = (
        Option("--active-only",
               "-a",
               dest="active_only",
               help="Display only active chroots",
               required=False,
               action="store_true",
               default=False),
    )
