import flask
import platform
from smtplib import SMTP
from email.mime.text import MIMEText
from coprs import app, helpers


class Message(object):
    subject = None
    text = None

    def __str__(self):
        return self.subject + "\n\n" + self.text


class PermissionRequestMessage(Message):
    def __init__(self, copr, applicant, permission_dict):
        """
        :param models.Copr copr:
        :param models.User applicant: object of a user that applies for new permissions (e.g. flask.g.user)
        :param models.CoprPermission permission: permission object
        :param dict permission_dict: {"old_builder": int, "old_admin": int, "new_builder": int, "new_admin": int}
        """
        self.subject = "[Copr] {0}: {1} is requesting permissions change".format(copr.full_name, applicant.name)

        self.text = "{0} asked for these changes:\n\n".format(applicant.name)

        for perm in ['Builder', 'Admin']:
            old = permission_dict.get("old_"+perm.lower())
            new = permission_dict.get("new_"+perm.lower())

            if old != new:
                if old is None:
                    old = 0 # previously unset
                self.text += "{0}: {1} -> {2}\n".format(
                    perm,
                    helpers.PermissionEnum(old),
                    helpers.PermissionEnum(new),
                )

        self.text += "\nProject: {0}".format(copr.full_name)


class PermissionChangeMessage(Message):
    def __init__(self, copr, permission_dict):
        """
        :param models.Copr copr:
        :param dict permission_dict: {"old_builder": int, "old_admin": int, "new_builder": int, "new_admin": int}
        """
        self.subject = "[Copr] {0}: Your permissions have changed".format(copr.full_name)
        self.text = "Your permissions have changed:\n\n"

        for perm in ['Builder', 'Admin']:
            old = permission_dict.get("old_"+perm.lower())
            new = permission_dict.get("new_"+perm.lower())
            if old != new:
                if old is None:
                    old = 0 # previously unset
                self.text += "{0}: {1} -> {2}\n".format(
                    perm, helpers.PermissionEnum(old),
                    helpers.PermissionEnum(new))

        self.text += "\nProject: {0}".format(copr.full_name)


class LegalFlagMessage(Message):
    def __init__(self, copr, reporter, reason):
        """
        :param models.Copr copr:
        :param models.User reporter: A person who reported the legal issue (e.g. flask.g.user)
        :param str reason: What is the legal issue?
        """
        self.subject = "Legal flag raised on {0}".format(copr.name)
        self.text = ("{0}\n"
                     "Navigate to {1}\n"
                     "Contact on owner is: {2} <{3}>\n"
                     "Reported by {4} <{5}>".format(
                        reason,
                        flask.url_for("admin_ns.legal_flag", _external=True),
                        copr.user.username,
                        copr.user.mail,
                        reporter.name,
                        reporter.mail))


class OutdatedChrootMessage(Message):
    def __init__(self, copr_chroots):
        """
        :param models.Copr copr:
        :param list copr_chroots: list of models.CoprChroot instances
        """
        self.subject = "[Copr] upcoming deletion of outdated chroots in your projects"
        self.text = ("You have been notified because you are an admin of projects, "
                     "that have some builds in outdated chroots\n\n"

                     "According to the 'Copr outdated chroots removal policy'\n"
                     "https://docs.pagure.org/copr.copr/copr_outdated_chroots_removal_policy.html\n"
                     "data are going to be preserved {0} days after the chroot is EOL "
                     "and then automatically deleted, unless you decide to prolong the expiration period.\n\n"

                     "Please, visit the projects settings if you want to extend the time.\n\n"
                     .format(app.config["DELETE_EOL_CHROOTS_AFTER"]))

        if not copr_chroots:
            raise AttributeError("No outdated chroots to notify about")

        for chroot in copr_chroots:
            url = helpers.fix_protocol_for_frontend(
                helpers.copr_url('coprs_ns.copr_repositories', chroot.copr, _external=True))
            self.text += (
                "Project: {0}\n"
                "Chroot: {1}\n"
                "Remaining: {2} days\n"
                "{3}\n\n".format(chroot.copr.full_name, chroot.name, chroot.delete_after_days, url))


def filter_allowlisted_recipients(recipients):
    """
    Filters e-mail recipients if the white list of recipients in conf is not empty.
    :param recipients: list of recipients
    :return: list of recipients who should receive an e-mail
    """
    if not app.config["ALLOWLIST_EMAILS"]:
        return recipients

    return [r for r in recipients if r in app.config["ALLOWLIST_EMAILS"]]


def send_mail(recipients, message, sender=None, reply_to=None):
    """
    :param list recipients: List of email recipients
    :param Message message:
    :param str sender: Email of a sender
    :return:
    """
    msg = MIMEText(message.text)
    msg["Subject"] = message.subject
    msg["From"] = sender or "root@{0}".format(platform.node())
    msg["To"] = ", ".join(recipients)
    msg.add_header("reply-to", reply_to or app.config["REPLY_TO"])
    recipients = filter_allowlisted_recipients(recipients)
    if not recipients:
        return
    with SMTP("localhost") as smtp:
        smtp.sendmail("root@{0}".format(platform.node()), recipients, msg.as_string())
