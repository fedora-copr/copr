import sqlalchemy
from flask_script import Command, Option
from coprs import db
from coprs.logic import builds_logic


class FailBuildCommand(Command):

    """
    Marks build as failed on all its non-finished chroots
    """

    option_list = [Option("build_id")]

    def run(self, build_id, **kwargs):
        try:
            builds_logic.BuildsLogic.mark_as_failed(build_id)
            print("Marking non-finished chroots of build {} as failed".format(build_id))
            db.session.commit()

        except (sqlalchemy.exc.DataError, sqlalchemy.orm.exc.NoResultFound) as e:
            print("Error: No such build {}".format(build_id))
            return 1
