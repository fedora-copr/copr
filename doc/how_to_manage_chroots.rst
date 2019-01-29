.. _how_to_manage_chroots:

How to manage chroots
======================

This article explains how to enable new chroots when a new Fedora is released and also how to disable them once the
particular Fedora version is not supported anymore.


Commands overview
-----------------

Chroots can be easily managed with these few commands.

::

    copr-frontend create_chroot <name>
    copr-frontend alter_chroot --action activate <name>
    copr-frontend alter_chroot --action deactivate <name>
    copr-frontend rawhide_to_release <rawhide-chroot> <newly-created-chroot>

However, `enablement process upon Fedora branching <#branching-process>`_ and also
`chroot deactivation when Fedora reaches it's EOL phase <#eol-deactivation-process>`_, are not that simple.
That's why the rest of this article explains the certain use-cases rather than atomic actions.


Branching process
-----------------

Immediately after Fedora branching, you want to do something like this

::

    copr-frontend create_chroot fedora-27-x86_64 fedora-27-i386 fedora-27-ppc64le


Copr uses `Mock <https://github.com/rpm-software-management/mock>`_ for building packages, so you should check if
the mock configs
`are already available <https://github.com/rpm-software-management/mock/tree/devel/mock-core-configs/etc/mock>`_
and in which version of the :code:`mock-core-configs` package they were added. If that version is not installed
on builders, you should temporarily disable the chroots.

::

    copr-frontend alter_chroot --action deactivate fedora-27-x86_64 fedora-27-i386 fedora-27-ppc64le


Projects can be configured to follow Fedora branching. That means, that once a chroot for new Fedora release is
enabled, it should be automatically turned-on for such projects. Moreover, builds from Rawhide should be forked into
this new chroot. It can be done like this

::

    copr-frontend rawhide_to_release fedora-rawhide-x86_64 fedora-27-x86_64
    copr-frontend rawhide_to_release fedora-rawhide-i386 fedora-27-i386
    copr-frontend rawhide_to_release fedora-rawhide-ppc64le fedora-27-ppc64le

Once the mock configs are available on the builders, you can re-enable the chroots

::

    copr-frontend alter_chroot --action activate fedora-27-x86_64 fedora-27-i386 fedora-27-ppc64le

When everything is done, `send an information email to a mailing list <#mailing-lists>`_.


.. _eol_deactivation_process:

EOL deactivation process
------------------------

When some Fedora version reaches the end of its release cycle and is marked as EOL, you can safely disable its chroots.
Though we want to keep the chroots enabled for a short period of time (few weeks) even after EOL, so our users can
comfortably deal with it. It can be done like this

::

    copr-frontend alter_chroot --action eol fedora-25-x86_64 fedora-25-i386 fedora-25-ppc64le

After running such command, no data are going to be removed. All repositories for the chroot are preserved. It is just
disabled and users can't build new packages in it anymore.

When it is done, `send an information email to a mailing list <#mailing-lists>`_.


Mailing lists
-------------

After adding or disabling chroots on the production instance, an information email about the action should be sent to
copr-devel@lists.fedorahosted.org . When doing both actions at the same time, describing it in one email is sufficient.
