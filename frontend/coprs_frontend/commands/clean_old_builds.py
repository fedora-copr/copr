from flask_script import Command
from coprs import db_session_scope
from coprs.logic.builds_logic import BuildsLogic


class DeleteOldBuilds(Command):
    """
    This garbage collects all builds which are "obsoleted" per user
    configuration, per models.Package.max_builds configuration.
    """

    # pylint: disable=method-hidden
    def run(self):
        with db_session_scope():
            BuildsLogic.clean_old_builds()
