from flask_script import Command
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.packages_logic import PackagesLogic


class DeleteOrphansCommand(Command):
    """
    Deletes builds and packages associated to deleted coprs.
    """

    def run(self):
        BuildsLogic.delete_orphaned_builds()
        PackagesLogic.delete_orphaned_packages()
