:orphan:

.. _copr_outdated_chroots_removal_policy:

Outdated chroots removal policy
===============================

This page describes the process of deleting build results in outdated chroots.


When a distribution (e.g. Fedora 26) officially reaches the end of its life, all its chroots
(e.g. fedora-26-x86_64, fedora-26-i386) get also disabled in Copr. This doesn't happen simultaneously,
instead, there is a small adjustment period of undocumented length, to give users enough time to migrate.

Once such chroots are disabled, new builds can no longer be submitted in them. Already existing build results
are still available and don't get removed at this point. By default, they are preserved for the next 180 days
after chroot disablement and then automatically removed. This can be suppressed for any project by any of its admins.

The remaining time can be restored back to 180 days at any moment, so the preservation period can be
periodically extended for an unlimited amount of time.
