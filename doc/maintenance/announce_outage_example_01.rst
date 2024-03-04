.. _outage_announce_01:

Upgrading packages
------------------

The Fedora Infra ticket and the e-mail may look like::

    Subject: Fedora Copr Outage - Updating to a <Month> <Year> Version
    ------------------------------------------------------------------

    There will be a Fedora Copr outage starting at

        $ date --date "2023-11-28 13:30 UTC"

    The outage will last approximately 2 hours.  The build queue processing will
    be stopped during the outage, and the Frontend/Web-UI will be down most of
    the time (no new tasks accepted).

    <EITHER>
    The DNF packages and repositories (hosted on copr-backend) will be available
    during this outage.

    <OR>
    The DNF packages and repositories (hosted on copr-backend) will be
    unavailable for a short period, about 10 minutes, as the copr-backend
    machine will be rebooted.

    Reason for outage:
    We will update the infrastructure machines to the latest packages that are
    currently being developed.

    Affected Services:
    https://copr.fedorainfracloud.org/
    https://download.copr.fedorainfracloud.org/results/

    Upstream ticket:
    https://github.com/fedora-copr/copr/issues/<ticket>

    <e-mail backref to infra ticket>
    Infrastructure ticket:
    https://pagure.io/fedora-infrastructure/issue/11468

    Please join Fedora Build System Matrix channel:
    https://matrix.to/#/#buildsys:fedoraproject.org

    Outage Contacts:
    @nikromen (Jiří Kyjovský) / @frostyx (Jakub Kadlčík) / @praiskup (Pavel Raiskup)

    Or comment on this ticket.
