"""
Fix unnoticed, but outdated chroots.
"""

import datetime
import click
from coprs import app, db
from coprs.logic.coprs_logic import CoprChrootsLogic


@click.command()
@click.option(
    "--prolong-days",
    type=int,
    metavar="N",
    show_default=True,
    default=app.config["EOL_CHROOTS_NOTIFICATION_PERIOD"]*2,
    help="The prolonged chroots will have N more days to let maintainers "
         "know.",
)
@click.option(
    "--delete-after-days",
    type=int,
    metavar="N",
    show_default=True,
    default=app.config["EOL_CHROOTS_NOTIFICATION_PERIOD"],
    help="Consider chroots that don't have delete_after in too far "
         "future, at most N days.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Don't change the database, and just print what would otherwise "
         "happen."
)
def fixup_unnoticed_chroots(dry_run, delete_after_days, prolong_days):
    """
    Just in case some of the outdated chroots got no e-mail notification so far
    - and the delte_after property has already passed -- give such chroot a bit
    more time so maintainers can be notified.  E.g. see issue#1724.
    """
    counter = 0
    query = CoprChrootsLogic.should_already_be_noticed(delete_after_days)

    new_delete_after = datetime.datetime.now() \
                     + datetime.timedelta(days=prolong_days)

    for copr_chroot in query:
        counter += 1
        current_after_days = copr_chroot.delete_after_days
        if current_after_days < 0:
            current_after_days = 0

        print("Prolonging {}/{} (id={}) by {} days".format(
            copr_chroot.copr.full_name,
            copr_chroot.name,
            copr_chroot.id,
            prolong_days - current_after_days))

        if dry_run:
            continue

        copr_chroot.delete_after = new_delete_after

    print("Prolonged {} chroots".format(counter))

    db.session.commit()
