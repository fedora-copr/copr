.. _how_to_manage_chroots:

How to manage chroots
======================

This article explains how to enable new chroots when a new Fedora is released and also how to disable them once the
particular Fedora version is not supported anymore.


Commands overview
-----------------

Chroots can be easily managed with these few commands.

::

    copr-frontend create-chroot <name>
    copr-frontend alter-chroot --action activate <name>
    copr-frontend alter-chroot --action deactivate <name>
    copr-frontend branch-fedora <new-branched-version>
    copr-frontend rawhide-to-release <rawhide-chroot> <newly-created-chroot>

However, `enablement process upon Fedora branching <#branching-process>`_ and also
`chroot deactivation when Fedora reaches it's EOL phase <#eol-deactivation-process>`_, are not that simple.
That's why the rest of this article explains the certain use-cases rather than atomic actions.


Branching process
-----------------

Projects can be configured to follow Fedora branching. That means, that once a
chroot for new Fedora release is enabled, it should be automatically turned-on
for such projects.  Moreover, builds from Rawhide should be forked into this new
chroot.

So **immediately** after Fedora branching (for exmaple to version **31**), you
want to do this (the command takes a very long time, be prepared)::

    copr-frontend branch-fedora 31

This command creates ``fedora-31-*`` chroots from corresponding
``fedora-rawhide-*`` chroots, and it also copies (duplicates/forks) latest
successful rawhide package builds into the new chroots.  This can be done
manually for each architecture by::

    copr-frontend create-chroot fedora-31-x86_64 --deactivated
    copr-frontend rawhide-to-release fedora-rawhide-x86_64 fedora-31-x86_64

From the manual steps you can see that the new chroots are **deactivated** at
the beginning.

It's important to do ``rawhide-to-release`` as soon as possible, because right
after branching action - Fedora Rawhide starts to live it's own separate life -
and the builds in Rawhide become more and more incompatible with the branched
Fedora.  So - if we copied the packages later - the branched chroot in copr
could become unusable.  You may consider sending an email to mailing list that
rawhide packages were copied.

The next needs to wait a bit, namely
* till there's a working compose for the freshly branched Fedora, and
* till the new mock configs are available on the builders.

Copr uses `Mock <https://github.com/rpm-software-management/mock>`_ for building packages, so you should check if
the mock configs
`are already available <https://github.com/rpm-software-management/mock/tree/devel/mock-core-configs/etc/mock>`_
and in which version of the :code:`mock-core-configs` package they were added. If that version is not installed
on builders, you should keep the chroots deactivated for now and continue later.

But the sooner we can enable the new chroots, the better -- all the builds that
happened in the time window between ``rawhide-to-release`` and chroot enablement
will be missed in the branched chroot later (users will have to rebuild them
manually).  So as soon as it is possible, do::

    copr-frontend alter-chroot --action activate fedora-32-x86_64 fedora-32-i386 \
        fedora-32-ppc64le fedora-32-aarch64 fedora-32-armhfp fedora-32-s390x

Update the the ``CHROOT_NAME_RELEASE_ALIAS`` option in the
``copr.conf`` stored in our ansible configuration and run the frontend
playbook. It should map the numeric ``$releasever`` value for Fedora
Rawhide to our existing chroots.

.. code-block:: python

    CHROOT_NAME_RELEASE_ALIAS = {
        "fedora-35": "fedora-rawhide",
    }

When everything is done, `send an information email to a mailing list <#mailing-lists>`_.


.. _eol_deactivation_process:

EOL deactivation process
------------------------

When some Fedora version reaches the end of its release cycle and is marked as EOL, you can safely disable its chroots.
Though we want to keep the chroots enabled for a short period of time (few weeks) even after EOL, so our users can
comfortably deal with it. It can be done like this

::

    copr-frontend alter-chroot --action eol fedora-31-x86_64 fedora-31-i386 \
        fedora-31-ppc64le fedora-31-aarch64 fedora-31-armhfp fedora-31-s390x

After running such command, no data are going to be removed. All repositories for the chroot are preserved. It is just
disabled and users can't build new packages in it anymore.

When it is done, `send an information email to a mailing list <#mailing-lists>`_.
See the :ref:`the disable chroots template <disable_chroots_template>`.


Mailing lists
-------------

After adding or disabling chroots on the production instance, an information email about the action should be sent to
copr-devel@lists.fedorahosted.org . When doing both actions at the same time, describing it in one email is sufficient.
