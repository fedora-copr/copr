.. _eol_logic:

Handling EOL CoprChroot entries
-------------------------------

There are currently three cases when we schedule a CoprChroot for removal but
preserve the data for some time to allow users to recover:

    1. User disables the chroot in a project ("unclicks" the checkbox).  We give
       them 14 days "preservation period" to reverse the decision without
       forcing them to rebuild everything.
    2. Copr Admin makes a chroot EOL, e.g., `fedora-38-x86_64` because the
       Fedora 38 version goes EOL.  We keep the builds for several months, and
       users can extend the preservation period.
    3. We disable rolling chroots (e.g., Fedora Rawhide or Fedora ELN) after a
       reasonable period of inactivity.

There are three database fields used for handling the EOL/preservation policies:
``CoprChroot.deleted`` (bool), ``CoprChroot.delete_after`` (timestamp),
and ``MockChroot.is_active`` (bool, 1:N mapped to ``CoprChroot``).  The
following table describes certain implications behind the logic:


.. table:: Logical implications per in-DB chroot state


    =========   ============    ======= ====================    =========       ===========
    is_active   delete_after    deleted e-mail |br|             can build       State && |br| Description
                                        notifications
    =========   ============    ======= ====================    =========       ===========
    yes         yes             yes     no                      no              |p_yel| ``preserved`` manual removal |p_end|
    yes         no              yes     --                      no              |p_red| ``deleted`` manual removal or rolling removal (or EOL removal, and reactivated) |p_end|
    yes         yes             no      yes                     yes             |p_yel| ``preserved`` rolling |p_end|
    yes         no              no      --                      yes             |p_gre| ``active`` normal chroot state |p_end|
    no          yes             yes     no                      no              |p_yel| ``preserved`` (deleted manualy, then mock chroot EOL or deactivation) |p_end|
    no          no              yes     --                      no              |p_red| ``deleted`` manually OR rolling deleted, and THEN EOLed/deactivated by Copr admin |p_end|
    no          yes             no      yes                     no              |p_yel| ``preserved`` mock chroot EOLed by Copr admin |p_end|
    no          no              no      --                      no              |p_gra| ``deactivated`` deactivated by Copr admin, data preserved |p_end|
    =========   ============    ======= ====================    =========       ===========

There's also a chroot state ``expired``, which is a special state of
the ``preserved`` state.  It is "still preserved", but the time for removal is
already there, namely ``now() >= delete_after``.

Note that when ``e-mail notifications`` are ``yes``, the time for removal has
come (``now() >= delete_after``) and we **were not** able to send the
notification e-mail, we **don't** remove the chroot data.  **No unexpected
removals.**
