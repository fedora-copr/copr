import sqlalchemy
import click
from coprs import db
from coprs.logic import builds_logic


@click.command()
@click.argument("build_id", type=int)
def fail_build(build_id):
    """
    Marks build as failed on all its non-finished chroots
    """

    try:
        builds_logic.BuildsLogic.mark_as_failed(build_id)
        print("Marking non-finished chroots of build {} as failed".format(build_id))
        db.session.commit()

    except (sqlalchemy.exc.DataError, sqlalchemy.orm.exc.NoResultFound) as e:
        print("Error: No such build {}".format(build_id))
        return 1
