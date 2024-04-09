.. _maintaining_distgit:

DistGit VM maintenance
======================

The Copr DistGit machine serves as a "proxy" middle-man between the actual source
code location and our farm of builders.  See :ref:`architecture` for more
info.  There's no data-consistency promise regarding Copr's DistGit data;
our primary goal is to ensure effective Copr Builds.  Consequently, we
only strive to keep the "proxy" sources for the **existing packages**
within still **existing Copr projects**.

Cleaning up DistGit
-------------------

Copr is a place where CI is done frequently, leading to the generation of
a significant amount of "source" data.  Often, each CI build produces a
different tarball that is uploaded and stored on the Copr DistGit machine.
Copr projects are also often short-lived (e.g., Packit).  This
necessitates Copr to conduct regular DistGit cleanup to prevent the source
data consumption from quickly exploding.

Currently, we have two house-cleaning procedures for DistGit:

1. `Cleaning up sources for outdated builds <https://github.com/fedora-copr/copr/blob/main/dist-git/run/dist-git-clear-tarballs.py>`_

2. `Cleaning up old repositories and sources for deleted Copr projects <https://github.com/fedora-copr/copr/blob/main/dist-git/run/prune-dist-git.py>`_

Both of these procedures are not enabled "by default" on every Copr
deployment.  However, Fedora Copr has automated these scripts using cron.

