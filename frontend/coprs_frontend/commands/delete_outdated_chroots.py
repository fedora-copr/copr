import click
from coprs import db
from coprs import app
from coprs.logic import coprs_logic, actions_logic
from coprs.helpers import ChrootDeletionStatus


@click.command()
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Do not actually remove any data, but rather print information on stdout"
)
def delete_outdated_chroots(dry_run):
    return delete_outdated_chroots_function(dry_run)


def delete_outdated_chroots_function(dry_run):
    """
    Delete data in all chroots that are considered as outdated. That means, the chroot is EOL
    and the preservation period is over because admin of the project didn't extend its duration.
    """

    deleter = DryRunDeleter() if dry_run else Deleter()

    chroots = coprs_logic.CoprChrootsLogic \
        .filter_to_be_deleted(coprs_logic.CoprChrootsLogic.get_multiple())
    for i, chroot in enumerate(chroots, start=1):

        # This shouldn't happen but we should play it safe, not just hope
        if chroot.delete_status != ChrootDeletionStatus("expired"):
            app.logger.error("Refusing to delete %s/%s because any notification was sent about its deletion",
                             chroot.copr.full_name, chroot.name)
            continue

        # This command will possibly delete a lot of chroots and can be a performance issue when committing
        # all at once. We are going to commit every x actions to avoid that.
        if i % 1000 == 0:
            deleter.commit()
        deleter.delete(chroot)
    deleter.commit()


class Deleter(object):
    def delete(self, chroot):
        actions_logic.ActionsLogic.send_delete_chroot(chroot)
        chroot.delete_after = None

    def commit(self):
        db.session.commit()


class DryRunDeleter(object):
    def delete(self, chroot):
        print("Add delete_chroot action for {} in {}".format(chroot.name, chroot.copr.full_name))

    def commit(self):
        pass
