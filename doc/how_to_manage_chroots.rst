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
    copr-frontend chroots-template [--template PATH]

However, `enablement process upon Fedora branching <#branching-process>`_ and also
`chroot deactivation when Fedora reaches it's EOL phase <#eol-deactivation-process>`_, are not that simple.
That's why the rest of this article explains the certain use-cases rather than atomic actions.


Branching process
-----------------

Projects can be configured to follow Fedora branching. That means, that once a
chroot for new Fedora release is enabled, it should be automatically turned-on
for such projects.  Moreover, builds from Rawhide should be forked into this new
chroot.

So **before** Fedora branching happens (for exmaple to version **31**), you want
to run the following command on Copr Frontend, under the ``copr-fe`` user::

    $ copr-frontend branch-fedora 31

This command takes a long time — even tens of minutes.  And then processing of
all the actions on the backend side will take about a day or so!  Be prepared to
this.

This command creates ``fedora-31-*`` chroots from the corresponding
``fedora-rawhide-*`` chroots, and it also copies (duplicates/forks) the latest
successful rawhide package builds into the new chroots.

This could be done also manually for each supported architecture like::

    copr-frontend create-chroot fedora-31-x86_64 --deactivated
    copr-frontend rawhide-to-release fedora-rawhide-x86_64 fedora-31-x86_64

From the manual steps you can see that the new chroots are **deactivated** at
the beginning.

It's important to do the ``branch-fedora`` action before the branching in Fedora
happens because the builds with bumped ``%dist`` did not happen yet -- and the
copied packages in the new (Fedora 31) chroots will have the old dist tag
(``.fc31``, not ``.fc32``).

Copr uses `Mock <https://github.com/rpm-software-management/mock>`_ for building packages, so you should check if
the mock configs
`are already available <https://github.com/rpm-software-management/mock/tree/devel/mock-core-configs/etc/mock>`_
and in which version of the :code:`mock-core-configs` package they were added.
This package needs to be on the Copr builders.

Now activate the new chroots (ASAP after all the builds were copied, you can
check the `FE statistics`_ page if the Actions peak is processed)::

    copr-frontend alter-chroot --action activate fedora-31-x86_64 fedora-31-i386 \
        fedora-31-ppc64le fedora-31-aarch64 fedora-31-armhfp fedora-31-s390x

The sooner this is done the better.  Since the ``branch-fedora`` action have
been executed, there have been a time window when users kept building **new
builds** into the "being forked" Rawhide chroots, and those new builds will
**not be copied** into the branched chroots.  The longer the activation takes,
the more inconsistent the branched chroot is.

Note that you don't have to care about the new (F31) official Fedora compose
creation time at all, the ``mock-core-configs`` package (and deps, like
``distribution-gpg-keys``) is prepared so both the Rawhide and the new branched
chroot (31) will work during the tranisition period (both before and after the
branched chroot has it's first own mirroed compose, see the `rel-eng thread`_
when this was tested).

When everything is done, `send an information email to a mailing list <#mailing-lists>`_.


.. _eol_deactivation_process:

EOL deactivation process
------------------------

When some Fedora version reaches the end of its release cycle and is marked as EOL, you can safely disable its chroots.
Though we want to keep the chroots enabled for a short period of time (few weeks) even after EOL, so our users can
comfortably deal with it. It can be done like this

::

    fv=34
    copr-frontend alter-chroot --action eol fedora-$fv-x86_64 fedora-$fv-i386 \
        fedora-$fv-ppc64le fedora-$fv-aarch64 fedora-$fv-armhfp fedora-$fv-s390x

After running such command, no data are going to be removed. All repositories for the chroot are preserved. It is just
disabled and users can't build new packages in it anymore.

When it is done, `send an information email to a mailing list <#mailing-lists>`_.
See the :ref:`the disable chroots template <disable_chroots_template>`.


.. _managing_chroot_comments:

Managing chroot comments
------------------------

Some of the available Mock chroots deserve a special care in documentation, e.g.
that `epel-8-*` chroots are nowadays built against Red Hat Enterprise Linux 8,
not CentOS 8 (which is EOL).  There's an administrator command for this::

    $ copr-frontend comment-chroot --chroot epel-8-x86_64 --comment '<strong>Built against RHEL 8!</strong>'

Note that HTML text is supported!

This was though a single-chroot command.  There's a better option for those Copr
instances that contain dozens of chroots::

    $ copr-frontend chroots-template [--template /etc/copr/chroots.conf]

This file reads the template file in the following format (a Python file
defining the ``config`` dictionary)::

    config = {}
    config["emulated"] = "This is an emulated chroot"
    config["rules"] = [{
        "match": "fedora-rawhide-i386",
        "comment": "This is soon to be removed",
    }, {
        "match": ["fedora-32", "fedora-33"],
        "comment": "<strong>Currently EOL</strong>, on your own risk",
    },
    {
        "match": ["aarch64", "ppc64le"],
        "match_type", "arch",
        "comment_append": "{{ emulated }}",
    }]

When (manually) executed, the command recursively iterates across all the active
Mock chroots, and applies the specified rules (only ``comment`` or
``comment_append`` currently) when the chroot matches the rules (``match`` and
``match_type`` statements).


Mailing lists
-------------

After adding or disabling chroots on the production instance, an information email about the action should be sent to
copr-devel@lists.fedorahosted.org . When doing both actions at the same time, describing it in one email is sufficient.

.. _`FE statistics`: https://copr.fedorainfracloud.org/status/stats/
.. _`rel-eng thread`: https://lists.fedoraproject.org/archives/list/rel-eng@lists.fedoraproject.org/thread/4NJDLL7KSACTRFT6TTURPRF2SI5N2STK/
