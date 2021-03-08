import click
from coprs import db
from coprs import app
from coprs.logic import coprs_logic, actions_logic


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
        if not is_safe_to_delete(chroot):
            app.logger.error("Refusing to delete %s/%s because any notification was sent about its deletion",
                             chroot.copr.full_name, chroot.name)
            continue

        # This command will possibly delete a lot of chroots and can be a performance issue when committing
        # all at once. We are going to commit every x actions to avoid that.
        if i % 1000 == 0:
            deleter.commit()
        deleter.delete(chroot)
    deleter.commit()


def is_safe_to_delete(copr_chroot):
    """
    Can we safely remove backend data for this chroot?
    This function **does not** contain the comprehensive list of checks whether
    a chroot is safe to delete. It merely checks if we sent a notification email
    about the chroot or if we didn't need to.
    """
    # In case the chroot is not EOL and somebody unclicked it from
    # a project, there is no protection. The data is safe to delete
    if copr_chroot.deleted:
        return True

    # Data for EOL chroots are safe to delete only if we tried to deliver
    # notifications about the upcoming deletion
    return bool(copr_chroot.delete_notify)


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
