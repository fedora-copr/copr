.. _email_templates:

Email templates
===============

Copr maintenance involves sending repetitive emails informing about various events such as announcing outages,
releases, disabling or enabling chroots, etc. This page contains templates of such email messages.
You are not forced to use them.


.. _disable_chroots_template:

Disable chroots
---------------

===============  ========================================================================
**Substitute:**  ``<VERSION>``, ``<DATE>``, ``<NAME>``
**Send to:**     ``copr-devel@lists.fedorahosted.org``, ``devel@lists.fedoraproject.org``
**Subject:**     ``Disabling Fedora <VERSION> chroots in Copr``
===============  ========================================================================

::

    Hello,

    we have just disabled Fedora <VERSION> chroots in Copr.

    According to the Fedora wiki [1], Fedora <VERSION> reached the end of its life
    on <DATE> and therefore we are disabling it in Copr.

    That effectively means that from this moment, it is no longer possible
    to submit builds for the following chroots:

    - fedora-<VERSION>-x86_64
    - fedora-<VERSION>-i386
    - fedora-<VERSION>-ppc64le
    - fedora-<VERSION>-aarch64
    - fedora-<VERSION>-armhfp
    - fedora-<VERSION>-s390x

    Additionally, according to Outdated chroots removal policy [2], Copr is
    going to preserve existing build results in those chroots for another
    180 days and then automatically remove them unless you take an action
    and prolong the chroots life span in your projects. Read more about this
    feature in the  Copr - Removing outdated chroots blog post [3].


    [1] https://fedoraproject.org/wiki/End_of_life
    [2] https://docs.pagure.org/copr.copr/copr_outdated_chroots_removal_policy.html
    [3] http://frostyx.cz/posts/copr-removing-outdated-chroots

    <NAME>
