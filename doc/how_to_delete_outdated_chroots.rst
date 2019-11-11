.. _how_to_delete_outdated_chroots:

How to delete outdated chroots
==============================

.. note:: All of these tasks are automatized for the main Copr instance in Fedora.
          This page might be rather useful for maintainers of other instances or developers enhancing this feature.

.. note:: Please read :ref:`copr_outdated_chroots_removal_policy` to see
          how the deletion of outdated chroots work from the user perspective.


This article explains how to mark a chroot as outdated, how to notify project owners, that some of their chroots are
outdated and going to be deleted in the future, and lastly how to actually delete them.


.. _mark_chroot_as_outdated:

Mark chroot as outdated
-----------------------

This step is described as :ref:`eol_deactivation_process` in the :ref:`how_to_manage_chroots` document.
To briefly summarize it, first, it is required to mark a chroot as EOL (aka outdated).

::

    copr-frontend alter-chroot --action eol fedora-25-x86_64

It doesn't matter whether the chroot is currently activated or deactivated, using ``--action eol``
always deactivates it. More importantly, for every related ``CoprChroot`` it generates a ``delete_after`` timestamp
saying when the copr chroot should be deleted.


Notify project admins
---------------------

Once the ``delete_after`` is set, the notification command starts to notice such copr chroot. The following command
prints to the stdout a list of people and about what they should be notified. Please be aware, that not only
project owners are going to be notified, but rather all project admins.

::

    copr-frontend notify-outdated-chroots --dry-run

When working on a non-production instance and wanting to really send the emails, filter the recipients to just yourself
or team members. Any *real* users shouldn't be contacted from devel instances!

::

    copr-frontend notify-outdated-chroots --dry-run -e myself@redhat.com

If this command prints that it would notify just the expected people (which were specified with the ``-e`` parameter),
then it is safe to run it without ``--dry-run`` parameter.

::

    copr-frontend notify-outdated-chroots -e myself@redhat.com


When the notification about a particular copr chroot is sent and then the ``notify-outdated-chroots`` command
is executed again, it will not send the notification for the second time. It is designed to be daily executed via Cron
and it needs to avoid spamming the people over and over again. Therefore when a notification is sent, a timestamp when
to send a next one is stored to the ``delete_notify`` column. In a case that this logic needs to be suppressed,
please use ``--all`` parameter. Then notifications are going to be sent regardless of the previous notification.


Delete the data
---------------

Once the ``delete_after`` timestamp is reached, the particular copr chroot should be deleted. To print
all the chroots for which this applies, use this command.

::

    copr-frontend delete-outdated-chroots --dry-run

To really delete them (i.e. creating an action which will delete the chroot directory on the backend),
run the command without ``--dry-run`` parameter.

::

    copr-frontend delete-outdated-chroots

When deleting the chroot (creating an action to delete the data on the backend), the ``delete_after``
and ``delete_notify`` columns are set to NULL and therefore ``notify-outdated-chroots``
and ``delete-outdated-chroots`` commands don't see the chroot anymore.


Automatization
--------------

This whole article is mainly for understanding how notifications and deletion of outdated
chroots work in order to debug or rework it. The only thing, that Copr administrator needs
to do manually is :ref:`mark_chroot_as_outdated`, everything else is achieved by a daily
cron script. See ``/etc/cron.daily/copr-frontend-optional``.
