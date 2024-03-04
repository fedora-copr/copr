.. _announcing_fedora_copr_outage:

Fedora Copr outage announcements
================================

This document is primarily intended for planning outages due to future
infrastructure updates.  However, in the event of any incidents or accidents
such as networking issues, IBM Cloud problems, Fedora Rawhide repository issues,
or any other matters that affect users, it's advisable to refer to this document
(possibly jump directly to the "Ongoing State" section).

.. warning::

    Schedule an outage even if it needs to occur within the next 5 minutes!

Please familiarize yourself with the `Fedora Outage SOP`_.  But in general,
follow the steps outlined in this document.

Planned outage
--------------

1. Red Hatters-only: Schedule a calendar event, and invite the ``Engineering
   Outage Calendar`` room.

2. Prepare `an infrastructure ticket
   <https://pagure.io/fedora-infrastructure/new_issue>`_ using one of these
   templates

   .. toctree::
       :maxdepth: 1

       Upgrading packages <announce_outage_example_01>

3. Send email to `copr-devel`_ mailing list informing about an upcomming
   release.  We usually copy-paste text of the infrastructure ticket, including
   a back-reference to the *infra ticket*.  Sending to::

       copr-devel@lists.fedorahosted.org
       copr-team@redhat.com
       OPT-IN buildsys@lists.fedoraproject.org
       OPT-IN devel@lists.fedoraproject.org

4. Adjust the `Matrix channel`_ title so it contains a message similar to::

        Planned outage 2022-08-17 20:00 UTC - https://pagure.io/fedora-infrastructure/issue/10854

5. Create a new "planned" `Fedora Status SOP`_ entry.

7. Create warning banner on Copr homepage::

     copr-frontend warning-banner --outage_time "2022-12-31 13:00-16:00 UTC" --ticket 1234


Ongoing outage
--------------

When the outage begins to cause real effects

1. Change the "planned" `Fedora Status SOP`_ entry into an "ongoing" entry.

2. Announce on `Matrix channel`_  — change title like
   ``s/Planned outage ../OUTAGE NOW .../`` and send some message like
   ``WARNING: The scheduled outage just begings!``.


Resolved outage
---------------

1. Remove the "Outage" note from the `Matrix channel`_ title, and send a message
   that the outage is over!

2. Send email to `copr-devel`_ mailing list.  If there is some important change
   you can send email to fedora devel mailing list too.  Mention the link to the
   "Highlights from XXXX-XX-XX release" documentation page.

3. Propose a new "highlights" post for the `Fedora Copr Blog`_,
   see `the example
   <https://github.com/fedora-copr/fedora-copr.github.io/pull/55/files>`_.

4. Close the Fedora Infra ticket.

5. Change the "ongoing" `Fedora Status SOP`_ entry into a "resolved" one.

6. Remove the warning banner from frontend page using
   ``copr-frontend warning-banner --remove``


.. _`copr-devel`: https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/
.. _`Fedora Outage SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/outage/
.. _`Fedora Status SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/status-fedora/
.. _`Fedora Copr Blog`: https://fedora-copr.github.io/
.. _`Matrix channel`: https://matrix.to/#/#buildsys:fedoraproject.org
