import datetime
from flask_script import Command, Option
from coprs import db
from coprs.logic import coprs_logic
from coprs.mail import send_mail, OutdatedChrootMessage


class NotifyOutdatedChrootsCommand(Command):
    """
    Notify all admins of projects with builds in outdated chroots about upcoming deletion.
    """
    option_list = [
        Option("--dry-run", action="store_true",
               help="Do not actually notify the people, but rather print information on stdout"),
        Option("-e", "--email", action="append", dest="email_filter",
               help="Notify only "),
        Option("-a", "--all", action="store_true",
               help="Notify all (even the recently notified) relevant people"),
    ]

    def run(self, dry_run, email_filter, all):
        self.email_filter = email_filter
        self.all = all
        notifier = DryRunNotifier() if dry_run else Notifier()

        outdated = coprs_logic.CoprChrootsLogic.filter_outdated(coprs_logic.CoprChrootsLogic.get_multiple())
        for user, chroots in self.get_user_chroots_map(outdated).items():
            chroots = self.filter_chroots([chroot for chroot in chroots])
            notifier.notify(user, chroots)
            notifier.store_timestamp(chroots)

    def get_user_chroots_map(self, chroots):
        user_chroot_map = {}
        for chroot in chroots:
            for admin in coprs_logic.CoprPermissionsLogic.get_admins_for_copr(chroot.copr):
                if self.email_filter and admin.mail not in self.email_filter:
                    continue
                if admin not in user_chroot_map:
                    user_chroot_map[admin] = []
                user_chroot_map[admin].append(chroot)
        return user_chroot_map

    def filter_chroots(self, chroots):
        if self.all:
            return chroots

        filtered = []
        for chroot in chroots:
            if not chroot.delete_notify:
                filtered.append(chroot)
                continue

            now = datetime.datetime.now()
            if (now - chroot.delete_notify).days >= 14:
                filtered.append(chroot)

        return filtered


class Notifier(object):
    def notify(self, user, chroots):
        msg = OutdatedChrootMessage(chroots)
        send_mail(user.mail, msg)

    def store_timestamp(self, chroots):
        for chroot in chroots:
            chroot.delete_notify = datetime.datetime.now()
        db.session.commit()


class DryRunNotifier(object):
    def notify(self, user, chroots):
        about = ["{0} ({1})".format(chroot.copr.full_name, chroot.name) for chroot in chroots]
        print("Notify {} about {}".format(user.mail, about))

    def store_timestamp(self, chroots):
        pass
