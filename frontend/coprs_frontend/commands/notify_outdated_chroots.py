import sys
import datetime
import click
from coprs import db, app
from coprs.logic import coprs_logic
from coprs.mail import send_mail, OutdatedChrootMessage


@click.command()
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Do not actually notify the people, but rather print information on stdout"
)
@click.option(
    "--email", "-e", "email_filter",
    help="Notify only "
)
@click.option(
    "--all/--not-all",
    default=False,
    help="Notify all (even the recently notified) relevant people"
)
def notify_outdated_chroots(dry_run, email_filter, all):
    return notify_outdated_chroots_function(dry_run, email_filter, all)


def notify_outdated_chroots_function(dry_run, email_filter, all):
    """
    Notify all admins of projects with builds in outdated chroots about upcoming deletion.
    """

    if not dry_run:
        dev_instance_warning(email_filter)

    notifier = DryRunNotifier() if dry_run else Notifier()
    outdated = coprs_logic.CoprChrootsLogic.filter_outdated(coprs_logic.CoprChrootsLogic.get_multiple())
    user_chroots_map = get_user_chroots_map(outdated, email_filter).items()
    for i, (user, chroots) in enumerate(user_chroots_map, start=1):
        chroots = filter_chroots([chroot for chroot in chroots], all)
        if not chroots:
            continue
        chroots.sort(key=lambda x: x.copr.full_name)
        notifier.notify(user, chroots)

        # This command will possibly update a lot of chroots and can be a performance issue when committing
        # all at once. We are going to commit every x actions to avoid that.
        if i % 1000 == 0:
            notifier.commit()

    notifier.commit()

def get_user_chroots_map(chroots, email_filter):
    user_chroot_map = {}
    for chroot in chroots:
        for admin in coprs_logic.CoprPermissionsLogic.get_admins_for_copr(chroot.copr):
            if email_filter and admin.mail not in email_filter:
                continue
            if admin not in user_chroot_map:
                user_chroot_map[admin] = []
            user_chroot_map[admin].append(chroot)
    return user_chroot_map

def filter_chroots(chroots, all):
    if all:
        return chroots

    filtered = []
    for chroot in chroots:
        if not chroot.delete_notify:
            filtered.append(chroot)
            continue

        # Skip the chroot if was notified in less than `n` days
        now = datetime.datetime.now()
        if (now - chroot.delete_notify).days >= app.config["EOL_CHROOTS_NOTIFICATION_PERIOD"]:
            filtered.append(chroot)

    return filtered

def dev_instance_warning(email_filter):
    if app.config["ENV"] != "production" and not email_filter:
        sys.stderr.write("I will not let you send emails to all Copr users from the dev instance!\n")
        sys.stderr.write("Please use this command with -e myself@foo.bar\n")
        sys.exit(1)


class Notifier(object):
    def notify(self, user, chroots):
        msg = OutdatedChrootMessage(chroots)
        send_mail([user.mail], msg)

        # If `send_mail` didn't raise any exception,
        # we consider the email to be sent correctly
        for chroot in chroots:
            chroot.delete_notify = datetime.datetime.now()

    def commit(self):
        db.session.commit()


class DryRunNotifier(object):
    def notify(self, user, chroots):
        about = ["{0} ({1})".format(chroot.copr.full_name, chroot.name) for chroot in chroots]
        print("Notify {} about {}".format(user.mail, about))

    def commit(self):
        pass
